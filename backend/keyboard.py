from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Кнопки
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Информация")],
        [KeyboardButton(text="Подписка")],
        [KeyboardButton(text="Отправить конспект")]
    ],
    resize_keyboard=True
)
