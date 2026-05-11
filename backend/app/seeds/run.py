from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AsyncSessionLocal, engine
from app.seeds.default_admin import seed_default_admin
from app.seeds.default_departments import seed_default_departments
from app.seeds.phase_doc_templates import seed_phase_doc_templates
from app.seeds.workflow_templates import seed_workflow_templates

SeedFn = Callable[[AsyncSession], Awaitable[int]]

SEED_TARGETS: dict[str, tuple[tuple[str, SeedFn], ...]] = {
    "admin": (("admin", seed_default_admin),),
    "deps": (("deps", seed_default_departments),),
    "phases": (("phases", seed_phase_doc_templates),),
    "workflows": (("workflows", seed_workflow_templates),),
    "all": (
        ("deps", seed_default_departments),
        ("admin", seed_default_admin),
        ("phases", seed_phase_doc_templates),
        ("workflows", seed_workflow_templates),
    ),
}


async def run_seed(target: str) -> dict[str, int]:
    if target not in SEED_TARGETS:
        raise ValueError(f"Unknown seed target: {target}")

    results: dict[str, int] = {}
    async with AsyncSessionLocal() as session:
        async with session.begin():
            for name, seed_fn in SEED_TARGETS[target]:
                results[name] = await seed_fn(session)
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed initial application data.")
    parser.add_argument("--target", choices=tuple(SEED_TARGETS.keys()), default="all")
    return parser


async def run_cli(target: str) -> dict[str, int]:
    try:
        return await run_seed(target)
    finally:
        await engine.dispose()


def main() -> None:
    args = build_parser().parse_args()
    results = asyncio.run(run_cli(args.target))
    print(json.dumps({"target": args.target, "inserted": results}, ensure_ascii=True))


if __name__ == "__main__":
    main()
