from fastapi import FastAPI, Query
from pydantic import BaseModel
from datetime import datetime, timedelta, time
from typing import List, Dict, Tuple, Optional, Union
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import calendar

# Создаем приложение FastAPI
app = FastAPI(
    title="Delivery Time API",
    description="API для расчета времени доставки заказов"
)

# Настраиваем CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Определяем исключения
class StoreNotFoundError(Exception):
    pass

class NoDeliveryScheduleError(Exception):
    pass

class StoreClosedError(Exception):
    pass

# Класс магазина
class Store:
    def __init__(self, code: str, working_hours: Dict[str, Tuple[int, int]], unloading_time: int):
        self.code = code
        self.working_hours = working_hours
        self.unloading_time = unloading_time
        self.special_schedules = {}
        self.closed_dates = set()

    def add_special_schedule(self, date: str, hours: Tuple[int, int]):
        self.special_schedules[date] = hours

    def add_closed_date(self, date: str):
        self.closed_dates.add(date)

    def is_open(self, date: datetime) -> bool:
        date_str = date.strftime("%Y-%m-%d")
        return date_str not in self.closed_dates

    def get_working_hours(self, date: datetime) -> Optional[Tuple[int, int]]:
        if not self.is_open(date):
            return None
        date_str = date.strftime("%Y-%m-%d")
        if date_str in self.special_schedules:
            return self.special_schedules[date_str]
        day_name = calendar.day_name[date.weekday()]
        return self.working_hours.get(day_name)

# Класс расписания доставки
class DeliverySchedule:
    def __init__(self, store_code: str, day_of_week: str, frequency: int, 
                 start_date: datetime, departure_time: time, 
                 travel_days: int, arrival_time: time):
        self.store_code = store_code
        self.day_of_week = day_of_week
        self.frequency = frequency
        self.start_date = start_date
        self.departure_time = departure_time
        self.travel_days = travel_days
        self.arrival_time = arrival_time
        self.day_of_week_num = list(calendar.day_name).index(day_of_week)

# Основная логика расчетов
class LogisticsSystem:
    def __init__(self, order_processing_time: int):
        self.stores: Dict[str, Store] = {}
        self.delivery_schedules: Dict[str, List[DeliverySchedule]] = {}
        self.order_processing_time = order_processing_time

    def add_store(self, store: Store):
        self.stores[store.code] = store

    def add_delivery_schedule(self, schedule: DeliverySchedule):
        self.delivery_schedules.setdefault(schedule.store_code, []).append(schedule)

    def get_next_delivery_dates(self, store_code: str, from_date: datetime, count: int = 3) -> List[Tuple[DeliverySchedule, datetime]]:
        schedules = self.delivery_schedules.get(store_code)
        if not schedules:
            raise NoDeliveryScheduleError("No delivery schedule found for this store.")
        delivery_dates = []
        current_date = from_date
        while len(delivery_dates) < count and (current_date - from_date).days < 60:
            for schedule in schedules:
                if current_date.weekday() == schedule.day_of_week_num:
                    weeks_diff = ((current_date - schedule.start_date).days // 7)
                    if weeks_diff % schedule.frequency == 0 and current_date >= schedule.start_date:
                        if current_date.date() == from_date.date() and schedule.departure_time < from_date.time():
                            continue
                        arrival_date = current_date + timedelta(days=schedule.travel_days)
                        arrival_datetime = datetime.combine(arrival_date.date(), schedule.arrival_time)
                        delivery_dates.append((schedule, arrival_datetime))
                        if len(delivery_dates) >= count:
                            break
            current_date += timedelta(days=1)
        return sorted(delivery_dates, key=lambda x: x[1])

    def get_pickup_times(self, store_code: str, delivery_datetime: datetime) -> Optional[Tuple[datetime, datetime]]:
        store = self.stores.get(store_code)
        if not store:
            raise StoreNotFoundError("Store not found.")
        unloading_time_delta = timedelta(minutes=store.unloading_time)
        available_time = delivery_datetime + unloading_time_delta
        working_hours = store.get_working_hours(available_time.date())
        if not working_hours:
            raise StoreClosedError("Store is closed on delivery date.")
        opening_time = time(working_hours[0], 0)
        closing_time = time(working_hours[1], 0)
        if available_time.time() >= closing_time:
            next_day = available_time.date() + timedelta(days=1)
            next_day_hours = store.get_working_hours(next_day)
            if not next_day_hours:
                raise StoreClosedError("Store is closed on the next day after delivery.")
            start_time = datetime.combine(next_day, time(next_day_hours[0], 0))
            end_time = datetime.combine(next_day, time(next_day_hours[1], 0))
            return (start_time, end_time)
        if available_time.time() < opening_time:
            start_time = datetime.combine(available_time.date(), opening_time)
        else:
            start_time = available_time
        end_time = datetime.combine(available_time.date(), closing_time)
        return (start_time, end_time)

    def get_delivery_dates(self, store_code: str, order_date: datetime, days_to_show: int = 5) -> Dict[str, Union[List[Dict], Dict]]:
        store = self.stores.get(store_code)
        if not store:
            return {"error": "Store not found"}
        
        ready_datetime = order_date + timedelta(minutes=self.order_processing_time)
        
        try:
            delivery_dates = self.get_next_delivery_dates(store_code, ready_datetime, days_to_show * 2)
        except NoDeliveryScheduleError as e:
            return {"error": str(e)}
        
        result = []
        seen_dates = set()
        
        for schedule, delivery_date in delivery_dates:
            try:
                pickup_times = self.get_pickup_times(store_code, delivery_date)
            except StoreClosedError:
                continue
            
            if not pickup_times:
                continue
                
            start_time, end_time = pickup_times
            date_str = start_time.strftime("%Y-%m-%d")
            
            if date_str in seen_dates:
                continue
                
            seen_dates.add(date_str)
            
            result.append({
                "date": date_str,
                "time_range": [start_time.strftime("%H:%M"), end_time.strftime("%H:%M")],
                "formatted": f"{date_str} from {start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')}"
            })
            
            if len(result) >= days_to_show:
                break
                
        if not result:
            return {"error": "No available dates for pickup in the near future"}
        
        return {"dates": result}

# Модели данных для FastAPI
class DeliveryDatesResponse(BaseModel):
    date: str
    time_range: List[str]
    formatted: str

class DeliveryResult(BaseModel):
    dates: Optional[List[DeliveryDatesResponse]] = None
    error: Optional[str] = None

# Создаем тестовые данные
logistics_system = LogisticsSystem(order_processing_time=60)
store = Store(
    code="STORE001",
    working_hours={
        "Monday": (10, 20),
        "Tuesday": (10, 20),
        "Wednesday": (10, 20),
        "Thursday": (10, 20),
        "Friday": (10, 20),
        "Saturday": (10, 18),
        "Sunday": (10, 17)
    },
    unloading_time=120
)
store.add_closed_date("2024-07-01")
store.add_special_schedule("2024-07-02", (12, 16))
logistics_system.add_store(store)
schedule1 = DeliverySchedule(
    store_code="STORE001",
    day_of_week="Monday",
    frequency=1,
    start_date=datetime(2024, 6, 1),
    departure_time=datetime.strptime("08:00", "%H:%M").time(),
    travel_days=2,
    arrival_time=datetime.strptime("09:00", "%H:%M").time()
)
schedule2 = DeliverySchedule(
    store_code="STORE001",
    day_of_week="Thursday",
    frequency=1,
    start_date=datetime(2024, 6, 1),
    departure_time=datetime.strptime("08:00", "%H:%M").time(),
    travel_days=1,
    arrival_time=datetime.strptime("10:00", "%H:%M").time()
)
logistics_system.add_delivery_schedule(schedule1)
logistics_system.add_delivery_schedule(schedule2)

# API Endpoint
@app.get("/delivery_times/", response_model=DeliveryResult)
def get_delivery_times(
    store_code: str = Query(..., description="Код магазина"),
    order_date: Optional[datetime] = Query(None, description="Дата и время заказа (формат: YYYY-MM-DDTHH:MM)")
):
    """
    Получить возможные даты доставки заказа
    """
    if order_date is None:
        order_date = datetime.now()
    result = logistics_system.get_delivery_dates(store_code, order_date)
    if "dates" in result:
        return {"dates": result["dates"], "error": None}
    else:
        return {"dates": [], "error": result["error"]}

# Дополнительный эндпоинт с корректной кодировкой
@app.get("/")
def read_root():
    return {"message": "Welcome to Delivery Time API! Go to /docs for documentation."}
