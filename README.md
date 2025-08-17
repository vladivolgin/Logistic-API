# Logistic-API

## Получение информации о возможных датах доставки
 
Базовый запрос
```
GET /delivery_times/?store_code=STORE001
```
С указанием даты заказа
```
GET /delivery_times/?store_code=STORE001&order_date=2025-06-27T15:30
```
## Пример ответа
```json
{
  "dates": [
    {
      "date": "2025-06-27",
      "time_range": ["12:00", "20:00"],
      "formatted": "2025-06-27 from 12:00 to 20:00"
    },
    {
      "date": "2025-07-02",
      "time_range": ["11:00", "20:00"],
      "formatted": "2025-07-02 from 11:00 to 20:00"
    }
  ],
  "error": null
}
```

