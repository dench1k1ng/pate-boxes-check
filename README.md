# pate-boxes-check

## Tortikipirogi

Для отдельного режима Tortikipirogi запусти:

```bash
python3 server_tortikipirogi.py
```

Открой `http://127.0.0.1:8001`. В Vercel режим доступен по адресу `/tortikipirogi`.

Для списков «Мамин хлеб» открой `/mamin-hleb`. Каждый заголовок «Сладкий бокс» или «Сытный бокс» становится карточкой по цене 1725 ₸ вместо 3450 ₸ (скидка 50%), а строки под ним сохраняются составом. Формат `Бокс N - цена` поддерживает индивидуальную цену каждого бокса: цена из строки считается скидочной, а оригинальная цена автоматически равна ей × 2 (скидка 50%); коэффициент задаётся в `PRICED_BOX_ORIGINAL_PRICE_MULTIPLIER`. `Сыганак 3` переключает карточки в `Royalty Coffee | Сыганак 3` и категорию `Кофейня`.

Поддерживаются смешанные форматы в одном сообщении:

```text
Трайфл медовый-760
Круассан с семгой 1800, со скидкой 1440
27.09 KULINAR&CA. Цена за 1 шт
Клаб сэндвич с курицей 665 вместо 950 (в наличии 2 шт)
```

Название заведения можно задать в поле над сообщением — оно применится ко всем товарам и имеет приоритет над заголовком сообщения. Если поле пустое, работает заголовок с датой и названием заведения. В формате `цена вместо оригинала` цены сохраняются напрямую, а количество берётся из `(в наличии N шт)`. В коротком формате оригинальная цена считается как цена со скидкой, делённая на 0.8. Количество без явного `шт`/`порция` равно 1. Фото не добавляются автоматически.

# Запуск сайта

cd /home/shindenis/programming-projects/pate
python3 server.py

Тесты:
python3 -m py_compile server.py parse_daily.py upload_to_crm.py
python3 -m unittest discover -s tests -v
curl -s -X POST <http://127.0.0.1:8000/api/parse> ...

Старые без сайта именно скриптом тесты
cd /home/shindenis/programming-projects/pate
python3 -m pip install requests pymupdf pytesseract pillow --break-system-packages
cp config.example.json config.json
python3 -m unittest discover -s tests -v
python3 parse_daily.py message_examples.txt catalog_paste.json > result.json
python3 upload_to_crm.py result.json --config config.json --dry-run
