"""Основной Telegram-бот: приём архивов, валидация и ручная проверка."""

import logging
import logging.handlers
import os
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import telebot
from telebot import types

from check_context import CheckContext
from config_loader import load_config
from decision_engine import DecisionStatus, decide
from errors import ErrorDetail, ErrorCode, format_user_report
from google_service import update_sheet
from pdf_controller import PdfController
from qa_service import QaService
from structure_validator import StructureValidator
from title_page_analyzer import StubTitleAnalyzer, YoloTesseractTitleAnalyzer

# Путь к конфигу по умолчанию
CONFIG_PATH = "config.json"


@dataclass
class ManualQueueItem:
    # Элемент очереди ручной проверки
    item_id: int
    zip_path: str
    group: str
    student_short: str
    discipline_info: dict
    chat_id: int


class ManualQueue:
    def __init__(self) -> None:
        # Храним очередь в памяти (без БД)
        self._items: dict[int, ManualQueueItem] = {}
        self._counter = 0

    def add(self, item: ManualQueueItem) -> int:
        # Назначаем ID и сохраняем элемент
        self._counter += 1
        item.item_id = self._counter
        self._items[item.item_id] = item
        return item.item_id

    def get(self, item_id: int) -> Optional[ManualQueueItem]:
        return self._items.get(item_id)

    def remove(self, item_id: int) -> None:
        self._items.pop(item_id, None)

    def list_items(self) -> list[ManualQueueItem]:
        return list(self._items.values())


class PortfolioBot:
    def __init__(self, config_path: str) -> None:
        # Загружаем конфиг и инициализируем зависимости
        self.config = load_config(config_path).raw
        token = self.config["telegram"]["token"]
        self.bot = telebot.TeleBot(token, threaded=False)
        self.attempts: dict[int, int] = {}
        self.manual_queue = ManualQueue()
        self.validator = StructureValidator(self.config)
        self.pdf_controller = PdfController()
        self.title_analyzer = self._build_title_analyzer()
        self.qa_service = QaService(self.config)
        self.logger = logging.getLogger("bot")
        self._configure_logging()
        self._register_handlers()

    def _configure_logging(self) -> None:
        # Базовое логирование + опционально RotatingFileHandler
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        logging_config = self.config.get("logging", {})
        if logging_config.get("enable_file_logging"):
            logs_dir = Path(self.config["paths"]["logs_dir"])
            logs_dir.mkdir(parents=True, exist_ok=True)
            handler = logging.handlers.RotatingFileHandler(
                logs_dir / "app.log",
                maxBytes=int(logging_config.get("max_log_bytes", 2_000_000)),
                backupCount=int(logging_config.get("backup_count", 3)),
                encoding="utf-8",
            )
            handler.setLevel(logging.INFO)
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            logging.getLogger().addHandler(handler)

    def _build_title_analyzer(self):
        # В зависимости от конфигурации выбираем stub или YOLO+OCR
        title_cfg = self.config.get("title_check", {})
        if title_cfg.get("enabled") and title_cfg.get("backend") == "yolo":
            return YoloTesseractTitleAnalyzer(
                yolo_weights_path=title_cfg.get("yolo_weights_path", ""),
                tesseract_cmd=title_cfg.get("tesseract_cmd", ""),
            )
        return StubTitleAnalyzer()

    def _register_handlers(self) -> None:
        # Команды и обработчики сообщений/колбэков
        @self.bot.message_handler(commands=["start"])
        def handle_start(message):
            self.bot.send_message(
                message.chat.id,
                "Отправьте ZIP-архив с портфолио для проверки.",
            )

        @self.bot.message_handler(commands=["admin_help"])
        def handle_admin_help(message):
            # Помощь для администраторов
            if not self._is_admin(message.from_user.id):
                return
            self.bot.send_message(
                message.chat.id,
                "/manual_queue - список заявок на ручную проверку\n"
                "/manual_accept <id> - подтвердить и отметить\n"
                "/manual_reject <id> - отклонить",
            )

        @self.bot.message_handler(commands=["manual_queue"])
        def handle_manual_queue(message):
            # Показ очереди ручной проверки
            if not self._is_admin(message.from_user.id):
                return
            items = self.manual_queue.list_items()
            if not items:
                self.bot.send_message(message.chat.id, "Очередь ручной проверки пуста.")
                return
            lines = ["Очередь ручной проверки:"]
            for item in items:
                lines.append(
                    f"{item.item_id}: {item.group} / {item.student_short} / {item.discipline_info['discipline_full']}"
                )
            self.bot.send_message(message.chat.id, "\n".join(lines))

        @self.bot.message_handler(commands=["manual_accept"])
        def handle_manual_accept(message):
            # Ручное принятие заявки
            if not self._is_admin(message.from_user.id):
                return
            parts = message.text.split()
            if len(parts) != 2:
                self.bot.send_message(message.chat.id, "Укажите ID заявки.")
                return
            item = self.manual_queue.get(int(parts[1]))
            if not item:
                self.bot.send_message(message.chat.id, "Заявка не найдена.")
                return
            result = update_sheet(
                self.config,
                item.group,
                item.student_short,
                item.discipline_info,
            )
            if not result.success:
                self.bot.send_message(message.chat.id, "Не удалось отметить в журнале.")
                return
            self._move_to_storage(item.zip_path, item.group, item.student_short, item.discipline_info)
            self.manual_queue.remove(item.item_id)
            self.bot.send_message(item.chat_id, "Портфолио принято после ручной проверки.")
            self.bot.send_message(message.chat.id, "Готово.")

        @self.bot.message_handler(commands=["manual_reject"])
        def handle_manual_reject(message):
            # Ручное отклонение заявки
            if not self._is_admin(message.from_user.id):
                return
            parts = message.text.split()
            if len(parts) != 2:
                self.bot.send_message(message.chat.id, "Укажите ID заявки.")
                return
            item = self.manual_queue.get(int(parts[1]))
            if not item:
                self.bot.send_message(message.chat.id, "Заявка не найдена.")
                return
            if os.path.exists(item.zip_path):
                os.remove(item.zip_path)
            self.manual_queue.remove(item.item_id)
            self.bot.send_message(item.chat_id, "Портфолио отклонено после ручной проверки.")
            self.bot.send_message(message.chat.id, "Готово.")

        @self.bot.message_handler(content_types=["document"])
        def handle_document(message):
            # Основная точка входа для загрузки файлов
            self._handle_document(message)

        @self.bot.message_handler(content_types=["text"])
        def handle_text(message):
            # Ответы на вопросы студентов через базу знаний
            if message.text.startswith("/"):
                return
            self._handle_question(message)

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("manual_request:"))
        def handle_manual_request(call):
            # Кнопка ручной проверки просто подтверждает постановку в очередь
            self.bot.answer_callback_query(call.id, "Заявка уже в очереди ручной проверки.")

    def _is_admin(self, user_id: int) -> bool:
        # Проверяем, входит ли пользователь в список админов
        return user_id in self.config.get("admin", {}).get("admin_ids", [])

    def _handle_document(self, message) -> None:
        document = message.document
        # RAR архивы запрещены
        if document.file_name.lower().endswith(".rar"):
            self._register_failure(message.chat.id, message.from_user.id)
            self.bot.send_message(message.chat.id, "RAR-архивы не поддерживаются.")
            return
        # Поддерживаем только ZIP
        if not document.file_name.lower().endswith(".zip"):
            self._register_failure(message.chat.id, message.from_user.id)
            self.bot.send_message(message.chat.id, "Поддерживаются только ZIP-архивы.")
            return

        # Проверка размера
        if document.file_size > int(self.config["limits"]["max_zip_bytes"]):
            self._register_failure(message.chat.id, message.from_user.id)
            self.bot.send_message(message.chat.id, "Архив слишком большой.")
            return

        # Скачивание во временную папку
        temp_dir = Path(self.config["paths"]["temp_dir"])
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / document.file_name

        file_info = self.bot.get_file(document.file_id)
        file_data = self.bot.download_file(file_info.file_path)
        temp_path.write_bytes(file_data)

        # Валидируем структуру
        context = self.validator.validate(str(temp_path))
        if not context.errors:
            # Валидируем PDF и (опционально) титул
            self._validate_pdfs(context)

        # Принимаем решение
        decision = decide(context, self.config)

        if decision.status == DecisionStatus.REJECTED:
            # При отказе увеличиваем счётчик попыток
            self._register_failure(message.chat.id, message.from_user.id)
            report = format_user_report(context.errors)
            self.bot.send_message(message.chat.id, report.text)
            temp_path.unlink(missing_ok=True)
            return

        # Успешная проверка сбрасывает счётчик
        self._reset_attempts(message.from_user.id)

        if decision.status == DecisionStatus.ACCEPTED:
            # Пытаемся поставить отметку в Google Sheets (если включено)
            sheets_cfg = self.config.get("google_sheets", {})
            if sheets_cfg.get("enabled", True):
                sheet_result = update_sheet(
                    self.config,
                    context.group,
                    context.student_short,
                    self._discipline_info(context.discipline_full),
                )
                if not sheet_result.success:
                    # Ошибка Sheets переводит в ручную проверку
                    self._handle_manual_review(message.chat.id, context, str(temp_path))
                    return
            # Сохраняем в хранилище
            self._move_to_storage(str(temp_path), context.group, context.student_short, self._discipline_info(context.discipline_full))
            self.bot.send_message(message.chat.id, "Портфолио принято.")
            return

    def _validate_pdfs(self, context: CheckContext) -> None:
        # Проверка каждой PDF и опциональный анализ титула
        try:
            with zipfile.ZipFile(context.zip_path, "r") as archive:
                for pdf_path in context.pdf_paths:
                    error = self.pdf_controller.validate_pdf(archive, pdf_path)
                    if error:
                        context.errors.append(error)
                title_cfg = self.config.get("title_check", {})
                if title_cfg.get("enabled") and context.pdf_paths:
                    # Титул — первая PDF в списке
                    title_image = self.pdf_controller.extract_title_page(archive, context.pdf_paths[0])
                    if title_image is None:
                        context.errors.append(
                            ErrorDetail(
                                code=ErrorCode.INVALID_PDF,
                                message="Не удалось извлечь титульный лист PDF.",
                                path=context.pdf_paths[0],
                            )
                        )
                        return
                    context.title_analysis = self.title_analyzer.analyze(title_image)
        except zipfile.BadZipFile:
            context.errors.append(
                ErrorDetail(
                    code=ErrorCode.INVALID_ARCHIVE,
                    message="Файл не является корректным ZIP-архивом.",
                )
            )

    def _handle_manual_review(self, chat_id: int, context: CheckContext, temp_path: str) -> None:
        # Перемещаем архив в manual_review и ставим в очередь
        manual_root = Path(self.config["paths"]["manual_review_root"])
        manual_root.mkdir(parents=True, exist_ok=True)
        target_path = self._build_storage_path(manual_root, context, Path(temp_path).name)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(temp_path, target_path)
        item = ManualQueueItem(
            item_id=0,
            zip_path=str(target_path),
            group=context.group,
            student_short=context.student_short,
            discipline_info=self._discipline_info(context.discipline_full),
            chat_id=chat_id,
        )
        item_id = self.manual_queue.add(item)

        # Отправляем кнопку пользователю
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("На ручную проверку", callback_data=f"manual_request:{item_id}"))
        self.bot.send_message(
            chat_id,
            "Не удалось отметить в журнале. Отправьте на ручную проверку.",
            reply_markup=markup,
        )

    def _handle_question(self, message) -> None:
        # Ответ на текстовые вопросы через OpenAI и базу знаний
        try:
            result = self.qa_service.answer(message.text.strip())
        except Exception as exc:
            self.logger.exception("Ошибка при ответе на вопрос: %s", exc)
            self.bot.send_message(message.chat.id, "Не удалось обработать вопрос. Попробуйте позже.")
            return
        if not result.success:
            if result.error == "Missing OpenAI API key":
                self.bot.send_message(message.chat.id, "Справка временно отключена. Обратитесь к администратору.")
            elif result.error == "Rate limit exceeded":
                self.bot.send_message(message.chat.id, "Лимит запросов к справке исчерпан. Попробуйте позже.")
            else:
                self.bot.send_message(message.chat.id, "Справка сейчас недоступна.")
            return
        self.bot.send_message(message.chat.id, result.answer)

    def _move_to_storage(self, temp_path: str, group: str, student_short: str, discipline_info: dict) -> None:
        # Перемещаем архив в постоянное хранилище
        storage_root = Path(self.config["paths"]["storage_root"])
        target_path = storage_root / group / student_short / discipline_info["discipline_full"] / Path(temp_path).name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(temp_path, target_path)

    def _build_storage_path(self, root: Path, context: CheckContext, filename: str) -> Path:
        # Формируем путь хранения архива
        return root / context.group / context.student_short / context.discipline_full / filename

    def _discipline_info(self, discipline_full: str) -> dict:
        # Ищем дисциплину в справочнике
        for item in self.config["disciplines"]:
            if item["discipline_full"] == discipline_full:
                return item
        return {"discipline_full": discipline_full}

    def _register_failure(self, chat_id: int, user_id: int) -> None:
        # Увеличиваем счётчик неудач (в памяти)
        self.attempts[user_id] = self.attempts.get(user_id, 0) + 1
        if self.attempts[user_id] >= 3:
            # При 3 попытках — предложение ручной проверки
            self.attempts[user_id] = 0
            self.bot.send_message(
                chat_id,
                "Три неудачных попытки подряд. Предлагается ручная проверка.",
            )

    def _reset_attempts(self, user_id: int) -> None:
        # Успех сбрасывает счётчик
        self.attempts[user_id] = 0

    def run(self) -> None:
        # Запуск polling
        self.bot.infinity_polling(timeout=self.config["telegram"].get("polling_interval_sec", 1))


def main() -> None:
    # Точка входа
    bot = PortfolioBot(CONFIG_PATH)
    bot.run()


if __name__ == "__main__":
    main()
