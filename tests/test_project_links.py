"""Regression checks for stable, object-specific Mini App URLs."""

from src.services.project_links import canonical_project_name, object_card_url


def run() -> None:
    assert canonical_project_name("Михалковская") == "Реновация (Михалковская)"
    assert canonical_project_name("Хранилища") == "Хранилища"

    island_url = object_card_url("Остров-8")
    storage_url = object_card_url("Хранилища")
    renovation_url = object_card_url("Реновация")

    assert island_url != storage_url != renovation_url
    assert "%D0%9E%D1%81%D1%82%D1%80%D0%BE%D0%B2-8" in island_url
    assert "entity=" in island_url
    assert "%D0%A5%D1%80%D0%B0%D0%BD%D0%B8%D0%BB%D0%B8%D1%89%D0%B0" in storage_url
    print("Project link checks passed")


if __name__ == "__main__":
    run()
