"""SQLite persistence for the grocery catalog."""

from __future__ import annotations

from extract_server.db._ids import (
    blob_key,
    empty_sighting_id,
    is_valid_photo_id,
    new_photo_id,
    new_photo_ids,
)
from extract_server.db._product_fields import EDITABLE_FIELDS as _EDITABLE_FIELDS

EDITABLE_FIELDS = set(_EDITABLE_FIELDS)
from extract_server.db.connection import DB_PATH, close_all_connections, db_path, get_conn
from extract_server.db.extractions import (
    count_extractions,
    get_extraction,
    record_photo_extraction_failure,
    replace_photo_extraction,
    save_photo_extraction,
    set_extraction_pipeline_status,
)
from extract_server.db.photos import (
    delete_photo,
    find_photo_by_content_hash,
    get_photo,
    get_photo_blob_path,
    get_photo_store_location_id,
    prune_orphan_photo_files,
    save_photo,
    set_photo_store_location_id,
)
from extract_server.db.queries import (
    build_product_row,
    get_photos_extraction_status,
    list_product_rows,
)
from extract_server.db.sightings import (
    add_sighting,
    count_sightings_for_user,
    delete_sighting,
    delete_sightings_bulk,
    get_sighting,
    photo_id_for_empty_sighting,
    update_sighting,
)
from extract_server.db.user_stores import (
    CreateStoreResult,
    UserStoreLocation,
    count_photos_for_store,
    create_user_store,
    delete_user_store,
    get_user_store,
    list_user_stores,
    list_user_stores_as_dicts,
    store_as_match_dict,
    store_to_api_dict,
    update_user_store,
)
from extract_server.db.users import (
    User,
    authenticate_user,
    complete_onboarding,
    create_session,
    delete_session,
    get_user_by_id,
    get_user_id_for_session,
    list_onboarding_completed,
    register_user,
    remove_registered_user,
    verify_user_password,
)


def init_catalog_tables() -> None:
    from extract_server.db.extractions import init_extractions_table
    from extract_server.db.photos import init_photos_table
    from extract_server.db.sightings import init_sightings_table
    from extract_server.db.similarity import init_embeddings_table, init_relations_table

    init_photos_table()
    init_extractions_table()
    init_sightings_table()
    init_embeddings_table()
    init_relations_table()


def init_user_store_tables() -> None:
    from extract_server.db.user_stores import init_user_store_tables as _init

    _init()


def init_db() -> None:
    from extract_server.db.users import init_users_tables

    init_users_tables()
    init_user_store_tables()
    init_catalog_tables()


__all__ = [
    "DB_PATH",
    "EDITABLE_FIELDS",
    "CreateStoreResult",
    "User",
    "UserStoreLocation",
    "add_sighting",
    "authenticate_user",
    "blob_key",
    "build_product_row",
    "close_all_connections",
    "complete_onboarding",
    "count_extractions",
    "count_photos_for_store",
    "count_sightings_for_user",
    "create_session",
    "create_user_store",
    "db_path",
    "delete_photo",
    "delete_session",
    "delete_sighting",
    "delete_sightings_bulk",
    "delete_user_store",
    "empty_sighting_id",
    "find_photo_by_content_hash",
    "get_conn",
    "get_extraction",
    "get_photo",
    "get_photo_blob_path",
    "get_photo_store_location_id",
    "get_photos_extraction_status",
    "get_sighting",
    "get_user_by_id",
    "get_user_id_for_session",
    "get_user_store",
    "list_onboarding_completed",
    "init_db",
    "init_user_store_tables",
    "is_valid_photo_id",
    "list_product_rows",
    "list_user_stores",
    "list_user_stores_as_dicts",
    "new_photo_id",
    "new_photo_ids",
    "photo_id_for_empty_sighting",
    "prune_orphan_photo_files",
    "record_photo_extraction_failure",
    "register_user",
    "remove_registered_user",
    "replace_photo_extraction",
    "save_photo",
    "save_photo_extraction",
    "set_extraction_pipeline_status",
    "set_photo_store_location_id",
    "store_as_match_dict",
    "store_to_api_dict",
    "update_sighting",
    "update_user_store",
    "verify_user_password",
]
