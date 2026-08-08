from app.core.config import Settings
from app.db.session import create_database_engine, create_session_factory, transaction
from app.scripts._async import run_async
from app.services.demo_data import seed_demo_data


async def run() -> None:
    settings = Settings()
    if settings.app_env == "production":
        raise RuntimeError("Demo seed is disabled in production")

    engine = create_database_engine(settings)
    try:
        async with transaction(create_session_factory(engine)) as session:
            await seed_demo_data(session, settings)
    finally:
        await engine.dispose()


def main() -> None:
    run_async(run())
    print("Fictional demo seed completed.")


if __name__ == "__main__":
    main()
