import asyncio

from app.core.config import Settings
from app.db.session import create_database_engine, create_session_factory, transaction
from app.services.demo_data import reset_demo_data


async def run() -> None:
    settings = Settings()
    engine = create_database_engine(settings)
    try:
        async with transaction(create_session_factory(engine)) as session:
            await reset_demo_data(session, settings)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(run())
    print("Fictional demo reset completed.")


if __name__ == "__main__":
    main()
