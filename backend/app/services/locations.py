"""Reference list of Uzbekistan cities (pilot: city-to-city matching, no map API needed)."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Location

# (region_uz, region_ru, [(name_uz, name_ru, lat, lon), ...])
DATA = [
    ("Toshkent shahri", "г. Ташкент", [("Toshkent", "Ташкент", 41.2995, 69.2401)]),
    ("Toshkent viloyati", "Ташкентская обл.", [
        ("Chirchiq", "Чирчик", 41.4689, 69.5822),
        ("Olmaliq", "Алмалык", 40.8447, 69.5983),
        ("Angren", "Ангрен", 41.0167, 70.1436),
        ("Nurafshon", "Нурафшан", 41.0450, 69.3600),
        ("Bekobod", "Бекабад", 40.2214, 69.2697),
        ("Yangiyo'l", "Янгиюль", 41.1122, 69.0472),
    ]),
    ("Samarqand viloyati", "Самаркандская обл.", [
        ("Samarqand", "Самарканд", 39.6542, 66.9597),
        ("Kattaqo'rg'on", "Каттакурган", 39.8989, 66.2561),
        ("Urgut", "Ургут", 39.4022, 67.2431),
    ]),
    ("Buxoro viloyati", "Бухарская обл.", [
        ("Buxoro", "Бухара", 39.7747, 64.4286),
        ("Kogon", "Каган", 39.7228, 64.5517),
        ("G'ijduvon", "Гиждуван", 40.1000, 64.6833),
    ]),
    ("Andijon viloyati", "Андижанская обл.", [
        ("Andijon", "Андижан", 40.7821, 72.3442),
        ("Asaka", "Асака", 40.6415, 72.2387),
        ("Xonobod", "Ханабад", 40.8000, 73.0000),
    ]),
    ("Farg'ona viloyati", "Ферганская обл.", [
        ("Farg'ona", "Фергана", 40.3864, 71.7864),
        ("Qo'qon", "Коканд", 40.5286, 70.9425),
        ("Marg'ilon", "Маргилан", 40.4711, 71.7246),
        ("Quvasoy", "Кувасай", 40.3000, 71.9800),
    ]),
    ("Namangan viloyati", "Наманганская обл.", [
        ("Namangan", "Наманган", 40.9983, 71.6726),
        ("Chust", "Чуст", 41.0033, 71.2378),
        ("Pop", "Пап", 40.8736, 71.1089),
    ]),
    ("Jizzax viloyati", "Джизакская обл.", [
        ("Jizzax", "Джизак", 40.1158, 67.8422),
        ("G'allaorol", "Галляарал", 40.0260, 67.5940),
    ]),
    ("Sirdaryo viloyati", "Сырдарьинская обл.", [
        ("Guliston", "Гулистан", 40.4897, 68.7842),
        ("Yangiyer", "Янгиер", 40.2750, 68.8225),
        ("Shirin", "Ширин", 40.2167, 69.1167),
    ]),
    ("Qashqadaryo viloyati", "Кашкадарьинская обл.", [
        ("Qarshi", "Карши", 38.8606, 65.7891),
        ("Shahrisabz", "Шахрисабз", 39.0578, 66.8342),
        ("Kitob", "Китаб", 39.1200, 66.8800),
        ("G'uzor", "Гузар", 38.6200, 66.2500),
    ]),
    ("Surxondaryo viloyati", "Сурхандарьинская обл.", [
        ("Termiz", "Термез", 37.2242, 67.2783),
        ("Denov", "Денау", 38.2667, 67.9000),
        ("Sherobod", "Шерабад", 37.6667, 67.0000),
    ]),
    ("Navoiy viloyati", "Навоийская обл.", [
        ("Navoiy", "Навои", 40.0844, 65.3792),
        ("Zarafshon", "Зарафшан", 41.5733, 64.2017),
        ("Uchquduq", "Учкудук", 42.1567, 63.5556),
    ]),
    ("Xorazm viloyati", "Хорезмская обл.", [
        ("Urganch", "Ургенч", 41.5500, 60.6333),
        ("Xiva", "Хива", 41.3783, 60.3639),
    ]),
    ("Qoraqalpog'iston Respublikasi", "Республика Каракалпакстан", [
        ("Nukus", "Нукус", 42.4600, 59.6200),
        ("Beruniy", "Беруни", 41.6911, 60.7522),
        ("To'rtko'l", "Турткуль", 41.5500, 61.0000),
        ("Mo'ynoq", "Муйнак", 43.7683, 59.0214),
    ]),
]


async def seed_if_empty(session: AsyncSession) -> int:
    if await session.scalar(select(func.count(Location.id))):
        return 0
    n = 0
    for r_idx, (region_uz, region_ru, cities) in enumerate(DATA):
        for c_idx, (name_uz, name_ru, lat, lon) in enumerate(cities):
            session.add(
                Location(
                    region_uz=region_uz, region_ru=region_ru, name_uz=name_uz, name_ru=name_ru,
                    lat=lat, lon=lon, sort=r_idx * 100 + c_idx,
                )
            )
            n += 1
    return n


async def all_(session: AsyncSession) -> list[Location]:
    return list((await session.execute(select(Location).order_by(Location.sort))).scalars())
