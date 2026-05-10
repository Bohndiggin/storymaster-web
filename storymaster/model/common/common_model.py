"""Holds common model classes"""

from sqlalchemy import (
    Engine,
    Float,
    Integer,
    inspect,
)
from sqlalchemy.orm import Session, joinedload

from storymaster.model.database import base_connection, common_queries, schema


def _truncate(s: str, limit: int) -> str:
    """Trim long blob to a printable snippet (used by Storyweaver hover cards)."""
    if not s:
        return ""
    return s if len(s) <= limit else f"{s[:limit]}..."


def _truncate_block(s: str, limit: int) -> str:
    """Like _truncate but newline-prefixed; matches the controller's old format."""
    if not s:
        return ""
    return f"\n{s}" if len(s) <= limit else f"\n{s[:limit]}..."


class BaseModel:
    """The base model class for Models"""

    engine: Engine
    user_id: int

    # Mapping of table names to their corresponding ORM classes from the schema
    _table_to_class_map = {
        "user": schema.User,
        "storyline": schema.Storyline,
        "setting": schema.Setting,
        "storyline_to_setting": schema.StorylineToSetting,
        "litography_node": schema.LitographyNode,
        "node_connection": schema.NodeConnection,
        "litography_notes": schema.LitographyNotes,
        "litography_plot": schema.LitographyPlot,
        "litography_plot_section": schema.LitographyPlotSection,
        "litography_node_to_plot_section": schema.LitographyNodeToPlotSection,
        "litography_arc": schema.LitographyArc,
        "class": schema.Class_,
        "background": schema.Background,
        "race": schema.Race,
        "sub_race": schema.SubRace,
        "actor": schema.Actor,
        "actor_a_on_b_relations": schema.ActorAOnBRelations,
        "skills": schema.Skills,
        "actor_to_skills": schema.ActorToSkills,
        "faction": schema.Faction,
        "faction_a_on_b_relations": schema.FactionAOnBRelations,
        "faction_members": schema.FactionMembers,
        "location_": schema.Location,
        "location_to_faction": schema.LocationToFaction,
        "location_dungeon": schema.LocationDungeon,
        "location_city": schema.LocationCity,
        "location_city_districts": schema.LocationCityDistricts,
        "residents": schema.Resident,
        "location_flora_fauna": schema.LocationFloraFauna,
        "history": schema.History,
        "history_actor": schema.HistoryActor,
        "history_location": schema.HistoryLocation,
        "history_faction": schema.HistoryFaction,
        "object_": schema.Object_,
        "history_object": schema.HistoryObject,
        "object_to_owner": schema.ObjectToOwner,
        "world_data": schema.WorldData,
        "history_world_data": schema.HistoryWorldData,
        "litography_note_to_actor": schema.LitographyNoteToActor,
        "litography_note_to_background": schema.LitographyNoteToBackground,
        "litography_note_to_faction": schema.LitographyNoteToFaction,
        "litography_note_to_location": schema.LitographyNoteToLocation,
        "litography_note_to_history": schema.LitographyNoteToHistory,
        "litography_note_to_object": schema.LitographyNoteToObject,
        "litography_note_to_world_data": schema.LitographyNoteToWorldData,
        "litography_note_to_class": schema.LitographyNoteToClass,
        "litography_note_to_race": schema.LitographyNoteToRace,
        "litography_note_to_sub_race": schema.LitographyNoteToSubRace,
        "litography_note_to_skills": schema.LitographyNoteToSkills,
        "arc_to_node": schema.ArcToNode,
        "arc_to_actor": schema.ArcToActor,
        "alignment": schema.Alignment,
        "stat": schema.Stat,
        "actor_to_race": schema.ActorToRace,
        "actor_to_class": schema.ActorToClass,
        "actor_to_stat": schema.ActorToStat,
        "location_a_on_b_relations": schema.LocationAOnBRelations,
        "location_geographic_relations": schema.LocationGeographicRelations,
        "location_political_relations": schema.LocationPoliticalRelations,
        "location_economic_relations": schema.LocationEconomicRelations,
        "location_hierarchy": schema.LocationHierarchy,
        "actor_a_on_b_relations": schema.ActorAOnBRelations,
        "faction_a_on_b_relations": schema.FactionAOnBRelations,
        "arc_type": schema.ArcType,
        "arc_point": schema.ArcPoint,
        "document": schema.Document,
    }

    def __init__(self, user_id: int):
        self.engine = self.generate_connection()
        self.user_id = user_id

    def generate_connection(self) -> Engine:
        """Generates the connection used to test"""
        return base_connection.engine

    def load_user_storylines(self) -> list[int]:
        """Loads all the storyline_ids for a user"""
        with Session(self.engine) as session:
            storyline_id_list = session.execute(
                common_queries.get_storyline_ids_for_user(self.user_id)
            ).all()

        return [storyline.id for storyline in storyline_id_list]

    # --- Litographer Methods ---

    def get_litography_nodes(self, storyline_id: int) -> list[schema.LitographyNode]:
        """Fetches all litography nodes for a given storyline."""
        with Session(self.engine) as session:
            nodes = (
                session.query(schema.LitographyNode)
                .options(joinedload(schema.LitographyNode.storyline))
                .filter_by(storyline_id=storyline_id)
                .all()
            )
        return nodes

    # --- Lorekeeper Methods ---

    def get_all_table_names(self) -> list[str]:
        """
        Inspects the database and returns a list of user-visible table names.
        Filters out system tables and junction tables that shouldn't be directly edited.
        """
        inspector = inspect(self.engine)
        all_tables = inspector.get_table_names()

        # Tables that should be hidden from the Lorekeeper UI
        hidden_tables = {
            "user",
            "storyline",
            "setting",
            "storyline_to_setting",
            "litography_node",
            "litography_notes",
            "litography_plot",
            "litography_plot_section",
            "litography_node_to_plot_section",
            "litography_arc",
            "litography_note_to_actor",
            "litography_note_to_background",
            "litography_note_to_class",
            "litography_note_to_faction",
            "litography_note_to_history",
            "litography_note_to_location",
            "litography_note_to_object",
            "litography_note_to_race",
            "litography_note_to_sub_race",
            "litography_note_to_world_data",
            "history_actor",
            "history_location",
            "history_faction",
            "history_object",
            "history_world_data",
            "litography_note_to_skills",
            "arc_to_actor",
            "arc_to_node",
            "actor_to_race",
            "actor_to_class",
            "actor_to_stat",
        }

        return [table for table in all_tables if table not in hidden_tables]

    def get_table_data(
        self,
        table_name: str,
        storyline_id: int | None = None,
        setting_id: int | None = None,
    ) -> tuple[list[str], list[tuple]]:
        """
        Fetches all data from a specific table, optionally filtered by storyline_id or setting_id.
        If both are provided, setting_id takes precedence.
        """
        orm_class = self._table_to_class_map.get(table_name)

        if not orm_class:
            return [], []

        headers = [c.name for c in orm_class.__table__.columns]

        with Session(self.engine) as session:
            query = session.query(orm_class)

            # Filter by setting_id if the table has that column
            if hasattr(orm_class, "setting_id"):
                if setting_id:
                    # Direct setting_id filtering takes precedence
                    query = query.filter_by(setting_id=setting_id)
                elif storyline_id:
                    # Fall back to deriving setting_id from storyline_id
                    storyline_setting_link = (
                        session.query(schema.StorylineToSetting)
                        .filter_by(storyline_id=storyline_id)
                        .first()
                    )
                    if storyline_setting_link:
                        query = query.filter_by(
                            setting_id=storyline_setting_link.setting_id
                        )

            results = query.all()

            data = []
            for row_object in results:
                row_data = tuple(getattr(row_object, header) for header in headers)
                data.append(row_data)

        return headers, data

    def get_foreign_key_info(self, table_name: str) -> dict[str, tuple[str, str]]:
        """Gets foreign key relationships for a given table."""
        inspector = inspect(self.engine)
        fks = inspector.get_foreign_keys(table_name)
        fk_info = {}
        for fk in fks:
            local_column = fk["constrained_columns"][0]
            referred_table = fk["referred_table"]
            referred_column = fk["referred_columns"][0]
            fk_info[local_column] = (referred_table, referred_column)
        return fk_info

    def get_column_types(self, table_name: str) -> dict[str, str]:
        """Gets column types for a given table."""
        inspector = inspect(self.engine)
        columns = inspector.get_columns(table_name)

        column_types = {}
        for column in columns:
            column_name = column["name"]
            column_type = str(column["type"])

            # Normalize type names to standard categories
            if "INTEGER" in column_type.upper() or "INT" in column_type.upper():
                column_types[column_name] = "integer"
            elif (
                "FLOAT" in column_type.upper()
                or "REAL" in column_type.upper()
                or "DECIMAL" in column_type.upper()
                or "NUMERIC" in column_type.upper()
            ):
                column_types[column_name] = "float"
            elif "BOOLEAN" in column_type.upper() or "BOOL" in column_type.upper():
                column_types[column_name] = "boolean"
            elif "TEXT" in column_type.upper() or "CLOB" in column_type.upper():
                column_types[column_name] = "text"
            elif (
                "VARCHAR" in column_type.upper()
                or "CHAR" in column_type.upper()
                or "STRING" in column_type.upper()
            ):
                column_types[column_name] = "string"
            else:
                # Default to string for unknown types
                column_types[column_name] = "string"

        return column_types

    def get_row_by_id(self, table_name: str, row_id: int) -> dict | None:
        """Fetches a single row from a table by its primary key."""
        orm_class = self._table_to_class_map.get(table_name)
        if not orm_class:
            return None

        with Session(self.engine) as session:
            result = session.query(orm_class).filter_by(id=row_id).first()

        return result.as_dict() if result else None

    def get_all_rows_as_dicts(
        self,
        table_name: str,
        storyline_id: int | None = None,
        setting_id: int | None = None,
    ) -> list[dict]:
        """Fetches all rows from a table as dicts, optionally filtered by storyline or setting."""
        orm_class = self._table_to_class_map.get(table_name)
        if not orm_class:
            return []

        with Session(self.engine) as session:
            query = session.query(orm_class)

            # Filter by setting_id if the table has that column
            if hasattr(orm_class, "setting_id"):
                if setting_id:
                    # Direct setting_id filtering takes precedence
                    query = query.filter_by(setting_id=setting_id)
                elif storyline_id:
                    # Fall back to deriving setting_id from storyline_id
                    storyline_setting_link = (
                        session.query(schema.StorylineToSetting)
                        .filter_by(storyline_id=storyline_id)
                        .first()
                    )
                    if storyline_setting_link:
                        query = query.filter_by(
                            setting_id=storyline_setting_link.setting_id
                        )

            results = query.all()

        return [row.as_dict() for row in results]

    def get_all_storylines(self) -> list[schema.Storyline]:
        """Fetches all storylines from the database for the current user."""
        with Session(self.engine) as session:
            storylines = (
                session.query(schema.Storyline).filter_by(user_id=self.user_id).all()
            )
            return storylines

    def get_all_settings(self) -> list[schema.Setting]:
        """Fetches all settings from the database for the current user."""
        with Session(self.engine) as session:
            settings = (
                session.query(schema.Setting).filter_by(user_id=self.user_id).all()
            )
            return settings

    def get_all_users(self) -> list[schema.User]:
        """Fetches all users from the database."""
        with Session(self.engine) as session:
            users = session.query(schema.User).all()
            return users

    def create_user(self, username: str) -> schema.User:
        """Creates a new user in the database."""
        with Session(self.engine) as session:
            new_user = schema.User(username=username)
            session.add(new_user)
            session.commit()
            session.refresh(new_user)
            return new_user

    def delete_user(self, user_id: int):
        """Deletes a user and all related data from the database."""
        with Session(self.engine) as session:
            # Get the user
            user = session.query(schema.User).filter_by(id=user_id).first()
            if not user:
                raise ValueError(f"User with id {user_id} not found")

            # Delete all storylines for this user (cascade will handle related data)
            storylines = (
                session.query(schema.Storyline).filter_by(user_id=user_id).all()
            )
            for storyline in storylines:
                session.delete(storyline)

            # Delete all settings for this user (cascade will handle related data)
            settings = session.query(schema.Setting).filter_by(user_id=user_id).all()
            for setting in settings:
                session.delete(setting)

            # Delete the user
            session.delete(user)
            session.commit()

    def user_has_data(self, user_id: int) -> bool:
        """Checks if a user has any storylines or settings."""
        with Session(self.engine) as session:
            storyline_count = (
                session.query(schema.Storyline).filter_by(user_id=user_id).count()
            )
            setting_count = (
                session.query(schema.Setting).filter_by(user_id=user_id).count()
            )
            return storyline_count > 0 or setting_count > 0

    def get_user_by_id(self, user_id: int) -> schema.User | None:
        """Gets a user by ID."""
        with Session(self.engine) as session:
            return session.query(schema.User).filter_by(id=user_id).first()

    def switch_user(self, new_user_id: int) -> bool:
        """
        Switches the current user context to a different user.
        Returns True if successful, False if user doesn't exist.
        """
        # Verify the user exists
        user = self.get_user_by_id(new_user_id)
        if user:
            self.user_id = new_user_id
            return True
        return False

    def get_current_user(self) -> schema.User | None:
        """Gets the current user object."""
        return self.get_user_by_id(self.user_id)

    def update_row(self, table_name: str, data_dict: dict):
        """
        Updates a single row in the database.
        """
        orm_class = self._table_to_class_map.get(table_name)
        if not orm_class:
            raise ValueError(f"No ORM class found for table '{table_name}'")

        pk_value = data_dict.get("id")
        if pk_value is None:
            raise ValueError("Data for update must include an 'id' field.")

        with Session(self.engine) as session:
            item_to_update = (
                session.query(orm_class).filter_by(id=int(pk_value)).first()
            )

            if not item_to_update:
                raise ValueError(f"No item found in '{table_name}' with id {pk_value}")

            for key, value in data_dict.items():
                if key == "id":
                    continue

                if value == "" and key in orm_class.__table__.columns:
                    col_type = orm_class.__table__.columns[key].type
                    if isinstance(col_type, (Integer, Float)):
                        value = None

                setattr(item_to_update, key, value)

            session.commit()

    def add_row(
        self,
        table_name: str,
        data_dict: dict,
        storyline_id: int | None = None,
        setting_id: int | None = None,
    ):
        """
        Adds a new row to the database, associating it with the correct setting.
        If both storyline_id and setting_id are provided, setting_id takes precedence.
        """
        orm_class = self._table_to_class_map.get(table_name)
        if not orm_class:
            raise ValueError(f"No ORM class found for table '{table_name}'")

        if "id" in data_dict:
            del data_dict["id"]

        with Session(self.engine) as session:
            # If the table has a setting_id column, set it appropriately
            if hasattr(orm_class, "setting_id"):
                if setting_id:
                    # Direct setting_id takes precedence
                    data_dict["setting_id"] = setting_id
                elif storyline_id:
                    # Fall back to deriving setting_id from storyline_id
                    storyline_setting_link = (
                        session.query(schema.StorylineToSetting)
                        .filter_by(storyline_id=storyline_id)
                        .first()
                    )
                    if not storyline_setting_link:
                        raise ValueError(
                            f"No Setting found for Storyline ID {storyline_id}"
                        )
                    data_dict["setting_id"] = storyline_setting_link.setting_id

            # Convert empty strings to None for numeric types
            for key, value in data_dict.items():
                if value == "" and key in orm_class.__table__.columns:
                    col_type = orm_class.__table__.columns[key].type
                    if isinstance(col_type, (Integer, Float)):
                        data_dict[key] = None

            new_item = orm_class(**data_dict)
            session.add(new_item)
            session.commit()

    # Character Arc Management Methods
    def get_character_arcs(
        self, storyline_id: int | None = None
    ) -> list[schema.LitographyArc]:
        """Get all character arcs for a storyline"""
        with Session(self.engine) as session:
            query = session.query(schema.LitographyArc)

            if storyline_id:
                query = query.filter(schema.LitographyArc.storyline_id == storyline_id)

            return query.options(
                joinedload(schema.LitographyArc.arc_type),
                joinedload(schema.LitographyArc.actors).joinedload(
                    schema.ArcToActor.actor
                ),
            ).all()

    # Storyline-to-Setting Management Methods
    def get_settings_for_storyline(self, storyline_id: int) -> list[schema.Setting]:
        """Get all settings linked to a storyline"""
        with Session(self.engine) as session:
            storyline = (
                session.query(schema.Storyline)
                .filter(schema.Storyline.id == storyline_id)
                .options(
                    joinedload(schema.Storyline.storyline_to_settings).joinedload(
                        schema.StorylineToSetting.setting
                    )
                )
                .first()
            )

            if storyline:
                return [sts.setting for sts in storyline.storyline_to_settings]
            return []

    def get_storylines_for_setting(self, setting_id: int) -> list[schema.Storyline]:
        """Get all storylines linked to a setting"""
        with Session(self.engine) as session:
            setting = (
                session.query(schema.Setting)
                .filter(schema.Setting.id == setting_id)
                .options(
                    joinedload(schema.Setting.storyline_to_setting).joinedload(
                        schema.StorylineToSetting.storyline
                    )
                )
                .first()
            )

            if setting:
                return [sts.storyline for sts in setting.storyline_to_setting]
            return []

    def link_storyline_to_setting(self, storyline_id: int, setting_id: int) -> bool:
        """Link a storyline to a setting"""
        with Session(self.engine) as session:
            # Check if link already exists
            existing = (
                session.query(schema.StorylineToSetting)
                .filter(
                    schema.StorylineToSetting.storyline_id == storyline_id,
                    schema.StorylineToSetting.setting_id == setting_id,
                )
                .first()
            )

            if existing:
                return False  # Link already exists

            # Create new link
            link = schema.StorylineToSetting(
                storyline_id=storyline_id, setting_id=setting_id
            )
            session.add(link)
            session.commit()
            return True

    def unlink_storyline_from_setting(self, storyline_id: int, setting_id: int) -> bool:
        """Unlink a storyline from a setting"""
        with Session(self.engine) as session:
            link = (
                session.query(schema.StorylineToSetting)
                .filter(
                    schema.StorylineToSetting.storyline_id == storyline_id,
                    schema.StorylineToSetting.setting_id == setting_id,
                )
                .first()
            )

            if link:
                session.delete(link)
                session.commit()
                return True
            return False  # Link didn't exist

    def get_available_settings_for_storyline(
        self, storyline_id: int
    ) -> list[schema.Setting]:
        """Get all settings that could be linked to a storyline (not already linked)"""
        with Session(self.engine) as session:
            # Get all settings for this user
            all_settings = (
                session.query(schema.Setting)
                .filter(schema.Setting.user_id == self.user_id)
                .all()
            )

            # Get currently linked settings
            linked_settings = self.get_settings_for_storyline(storyline_id)
            linked_setting_ids = {setting.id for setting in linked_settings}

            # Return settings not already linked
            return [
                setting
                for setting in all_settings
                if setting.id not in linked_setting_ids
            ]

    def get_available_storylines_for_setting(
        self, setting_id: int
    ) -> list[schema.Storyline]:
        """Get all storylines that could be linked to a setting (not already linked)"""
        with Session(self.engine) as session:
            # Get all storylines for this user
            all_storylines = (
                session.query(schema.Storyline)
                .filter(schema.Storyline.user_id == self.user_id)
                .all()
            )

            # Get currently linked storylines
            linked_storylines = self.get_storylines_for_setting(setting_id)
            linked_storyline_ids = {storyline.id for storyline in linked_storylines}

            # Return storylines not already linked
            return [
                storyline
                for storyline in all_storylines
                if storyline.id not in linked_storyline_ids
            ]

    def get_character_arc(self, arc_id: int) -> schema.LitographyArc:
        """Get a specific character arc by ID"""
        with Session(self.engine) as session:
            arc = (
                session.query(schema.LitographyArc)
                .options(
                    joinedload(schema.LitographyArc.arc_type),
                    joinedload(schema.LitographyArc.actors).joinedload(
                        schema.ArcToActor.actor
                    ),
                )
                .filter(schema.LitographyArc.id == arc_id)
                .first()
            )

            if not arc:
                raise ValueError(f"Character arc with ID {arc_id} not found")
            return arc

    def get_arc_points(self, arc_id: int) -> list[schema.ArcPoint]:
        """Get all arc points for a character arc"""
        with Session(self.engine) as session:
            return (
                session.query(schema.ArcPoint)
                .options(joinedload(schema.ArcPoint.node))
                .filter(schema.ArcPoint.arc_id == arc_id)
                .order_by(schema.ArcPoint.order_index)
                .all()
            )

    def get_arc_types(self, setting_id: int | None = None) -> list[schema.ArcType]:
        """Get all arc types for a setting"""
        with Session(self.engine) as session:
            query = session.query(schema.ArcType)

            if setting_id:
                query = query.filter(schema.ArcType.setting_id == setting_id)

            return query.all()

    def create_character_arc(
        self,
        title: str,
        description: str,
        arc_type_id: int,
        storyline_id: int,
        actor_ids: list[int] | None = None,
    ) -> schema.LitographyArc:
        """Create a new character arc"""
        with Session(self.engine) as session:
            # Create the arc
            arc = schema.LitographyArc(
                title=title,
                description=description,
                arc_type_id=arc_type_id,
                storyline_id=storyline_id,
            )
            session.add(arc)
            session.flush()  # Get the ID

            # Link to actors if provided
            if actor_ids:
                for actor_id in actor_ids:
                    arc_to_actor = schema.ArcToActor(arc_id=arc.id, actor_id=actor_id)
                    session.add(arc_to_actor)

            session.commit()
            return arc

    def update_character_arc(
        self,
        arc_id: int,
        title: str | None = None,
        description: str | None = None,
        arc_type_id: int | None = None,
        actor_ids: list[int] | None = None,
    ) -> schema.LitographyArc:
        """Update an existing character arc"""
        with Session(self.engine) as session:
            arc = (
                session.query(schema.LitographyArc)
                .filter(schema.LitographyArc.id == arc_id)
                .first()
            )

            if not arc:
                raise ValueError(f"Character arc with ID {arc_id} not found")

            if title is not None:
                arc.title = title
            if description is not None:
                arc.description = description
            if arc_type_id is not None:
                arc.arc_type_id = arc_type_id

            # Update actor links if provided
            if actor_ids is not None:
                # Remove existing links
                session.query(schema.ArcToActor).filter(
                    schema.ArcToActor.arc_id == arc_id
                ).delete()

                # Add new links
                for actor_id in actor_ids:
                    arc_to_actor = schema.ArcToActor(arc_id=arc_id, actor_id=actor_id)
                    session.add(arc_to_actor)

            session.commit()
            return arc

    def delete_character_arc(self, arc_id: int):
        """Delete a character arc and all its arc points"""
        with Session(self.engine) as session:
            # Delete arc points first
            session.query(schema.ArcPoint).filter(
                schema.ArcPoint.arc_id == arc_id
            ).delete()

            # Delete actor links
            session.query(schema.ArcToActor).filter(
                schema.ArcToActor.arc_id == arc_id
            ).delete()

            # Delete the arc
            session.query(schema.LitographyArc).filter(
                schema.LitographyArc.id == arc_id
            ).delete()

            session.commit()

    def create_arc_point(
        self,
        arc_id: int,
        title: str,
        order_index: int,
        description: str | None = None,
        emotional_state: str | None = None,
        character_relationships: str | None = None,
        goals: str | None = None,
        internal_conflict: str | None = None,
        node_id: int | None = None,
    ) -> schema.ArcPoint:
        """Create a new arc point"""
        with Session(self.engine) as session:
            arc_point = schema.ArcPoint(
                arc_id=arc_id,
                title=title,
                order_index=order_index,
                description=description,
                emotional_state=emotional_state,
                character_relationships=character_relationships,
                goals=goals,
                internal_conflict=internal_conflict,
                node_id=node_id,
            )
            session.add(arc_point)
            session.commit()
            return arc_point

    def update_arc_point(self, arc_point_id: int, **kwargs) -> schema.ArcPoint:
        """Update an existing arc point"""
        with Session(self.engine) as session:
            arc_point = (
                session.query(schema.ArcPoint)
                .filter(schema.ArcPoint.id == arc_point_id)
                .first()
            )

            if not arc_point:
                raise ValueError(f"Arc point with ID {arc_point_id} not found")

            for key, value in kwargs.items():
                if hasattr(arc_point, key):
                    setattr(arc_point, key, value)

            session.commit()
            return arc_point

    def delete_arc_point(self, arc_point_id: int):
        """Delete an arc point"""
        with Session(self.engine) as session:
            session.query(schema.ArcPoint).filter(
                schema.ArcPoint.id == arc_point_id
            ).delete()
            session.commit()

    def create_arc_type(
        self, name: str, description: str, setting_id: int
    ) -> schema.ArcType:
        """Create a new arc type"""
        with Session(self.engine) as session:
            arc_type = schema.ArcType(
                name=name, description=description, setting_id=setting_id
            )
            session.add(arc_type)
            session.commit()
            return arc_type

    def get_arc_type(self, arc_type_id: int) -> schema.ArcType:
        """Get a specific arc type by ID"""
        with Session(self.engine) as session:
            arc_type = (
                session.query(schema.ArcType)
                .filter(schema.ArcType.id == arc_type_id)
                .first()
            )

            if not arc_type:
                raise ValueError(f"Arc type with ID {arc_type_id} not found")
            return arc_type

    def update_arc_type(
        self, arc_type_id: int, name: str | None = None, description: str | None = None
    ) -> schema.ArcType:
        """Update an existing arc type"""
        with Session(self.engine) as session:
            arc_type = (
                session.query(schema.ArcType)
                .filter(schema.ArcType.id == arc_type_id)
                .first()
            )

            if not arc_type:
                raise ValueError(f"Arc type with ID {arc_type_id} not found")

            if name is not None:
                arc_type.name = name
            if description is not None:
                arc_type.description = description

            session.commit()
            return arc_type

    def delete_arc_type(self, arc_type_id: int):
        """Delete an arc type and all character arcs using it"""
        with Session(self.engine) as session:
            # First delete all arc points for arcs using this type
            session.query(schema.ArcPoint).filter(
                schema.ArcPoint.arc_id.in_(
                    session.query(schema.LitographyArc.id).filter(
                        schema.LitographyArc.arc_type_id == arc_type_id
                    )
                )
            ).delete(synchronize_session=False)

            # Delete actor links for arcs using this type
            session.query(schema.ArcToActor).filter(
                schema.ArcToActor.arc_id.in_(
                    session.query(schema.LitographyArc.id).filter(
                        schema.LitographyArc.arc_type_id == arc_type_id
                    )
                )
            ).delete(synchronize_session=False)

            # Delete character arcs using this type
            session.query(schema.LitographyArc).filter(
                schema.LitographyArc.arc_type_id == arc_type_id
            ).delete()

            # Delete the arc type
            session.query(schema.ArcType).filter(
                schema.ArcType.id == arc_type_id
            ).delete()

            session.commit()

    def get_nodes_for_storyline(self, storyline_id: int) -> list[schema.LitographyNode]:
        """Get all nodes for a storyline"""
        with Session(self.engine) as session:
            return (
                session.query(schema.LitographyNode)
                .options(joinedload(schema.LitographyNode.storyline))
                .filter(schema.LitographyNode.storyline_id == storyline_id)
                .order_by(schema.LitographyNode.id)
                .all()
            )

    def get_actors_for_setting(self, setting_id: int) -> list[schema.Actor]:
        """Get all actors for a setting"""
        with Session(self.engine) as session:
            return (
                session.query(schema.Actor)
                .options(
                    joinedload(schema.Actor.setting),
                    joinedload(schema.Actor.background),
                    joinedload(schema.Actor.alignment),
                )
                .filter(schema.Actor.setting_id == setting_id)
                .order_by(schema.Actor.first_name, schema.Actor.last_name)
                .all()
            )

    def get_setting_by_id(self, setting_id: int) -> schema.Setting | None:
        """Gets a setting by ID."""
        with Session(self.engine) as session:
            return session.query(schema.Setting).filter_by(id=setting_id).first()

    def update_setting(self, setting_id: int, name: str = None, description: str = None) -> bool:
        """Updates a setting's name and/or description.

        Args:
            setting_id: The ID of the setting to update
            name: New name for the setting (optional)
            description: New description for the setting (optional)

        Returns:
            True if successful, False otherwise
        """
        try:
            with Session(self.engine) as session:
                setting = session.query(schema.Setting).filter_by(id=setting_id).first()
                if not setting:
                    return False

                if name is not None:
                    setting.name = name
                if description is not None:
                    setting.description = description

                session.commit()
                return True
        except Exception as e:
            print(f"Error updating setting: {e}")
            return False

    def delete_setting(self, setting_id: int) -> bool:
        """Deletes a setting and all related world-building data.

        Args:
            setting_id: The ID of the setting to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            with Session(self.engine) as session:
                setting = session.query(schema.Setting).filter_by(id=setting_id).first()
                if not setting:
                    return False

                # SQLAlchemy will handle cascading deletes based on relationships
                session.delete(setting)
                session.commit()
                return True
        except Exception as e:
            print(f"Error deleting setting: {e}")
            return False

    def get_storyline_by_id(self, storyline_id: int) -> schema.Storyline | None:
        """Gets a storyline by ID."""
        with Session(self.engine) as session:
            return session.query(schema.Storyline).filter_by(id=storyline_id).first()

    def update_storyline(self, storyline_id: int, name: str = None, description: str = None) -> bool:
        """Updates a storyline's name and/or description.

        Args:
            storyline_id: The ID of the storyline to update
            name: New name for the storyline (optional)
            description: New description for the storyline (optional)

        Returns:
            True if successful, False otherwise
        """
        try:
            with Session(self.engine) as session:
                storyline = session.query(schema.Storyline).filter_by(id=storyline_id).first()
                if not storyline:
                    return False

                if name is not None:
                    storyline.name = name
                if description is not None:
                    storyline.description = description

                session.commit()
                return True
        except Exception as e:
            print(f"Error updating storyline: {e}")
            return False

    def delete_storyline(self, storyline_id: int) -> bool:
        """Deletes a storyline and all related data.

        Args:
            storyline_id: The ID of the storyline to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            with Session(self.engine) as session:
                storyline = session.query(schema.Storyline).filter_by(id=storyline_id).first()
                if not storyline:
                    return False

                # SQLAlchemy will handle cascading deletes based on relationships
                session.delete(storyline)
                session.commit()
                return True
        except Exception as e:
            print(f"Error deleting storyline: {e}")
            return False

    def get_table_class(self, table_name: str):
        """Gets the SQLAlchemy ORM class for a given table name."""
        return self._table_to_class_map.get(table_name)

    # --- Node connection helpers --------------------------------------------
    # These exist so the Litographer controller doesn't need its own
    # `Session(self.model.engine)` blocks for connection ops. Phase 3 swaps
    # those bypasses to call these methods, which keeps the public seam
    # between desktop and web (BaseModel vs. BaseModelClient) clean.

    def get_node_connections(
        self, storyline_id: int
    ) -> list[schema.NodeConnection]:
        """Get every NodeConnection whose output node is in this storyline."""
        with Session(self.engine) as session:
            return (
                session.query(schema.NodeConnection)
                .join(
                    schema.LitographyNode,
                    schema.NodeConnection.output_node_id == schema.LitographyNode.id,
                )
                .filter(schema.LitographyNode.storyline_id == storyline_id)
                .all()
            )

    def create_node_connection(
        self, output_node_id: int, input_node_id: int
    ) -> schema.NodeConnection:
        """Create a NodeConnection if one doesn't already exist between the
        given output→input pair. Returns the existing or new row.
        """
        with Session(self.engine) as session:
            existing = (
                session.query(schema.NodeConnection)
                .filter_by(
                    output_node_id=output_node_id, input_node_id=input_node_id
                )
                .first()
            )
            if existing is not None:
                return existing
            connection = schema.NodeConnection(
                output_node_id=output_node_id, input_node_id=input_node_id
            )
            session.add(connection)
            session.commit()
            session.refresh(connection)
            return connection

    def delete_node_connection(self, connection_id: int) -> bool:
        """Delete a NodeConnection by id. Returns True if a row was removed."""
        with Session(self.engine) as session:
            connection = (
                session.query(schema.NodeConnection)
                .filter_by(id=connection_id)
                .first()
            )
            if connection is None:
                return False
            session.delete(connection)
            session.commit()
            return True

    # --- Plot / plot section helpers --------------------------------------
    # Phase 3a additions. Each replaces a `Session(self.model.engine)` block in
    # main_page_controller.py with a call into BaseModel — the same call works
    # against the HTTP API once swapped to BaseModelClient.

    def get_plots_for_storyline(
        self, storyline_id: int
    ) -> list[schema.LitographyPlot]:
        """Plots in a storyline, ordered by id."""
        with Session(self.engine) as session:
            return (
                session.query(schema.LitographyPlot)
                .filter_by(storyline_id=storyline_id)
                .order_by(schema.LitographyPlot.id)
                .all()
            )

    def get_plot(self, plot_id: int) -> schema.LitographyPlot | None:
        with Session(self.engine) as session:
            return session.query(schema.LitographyPlot).filter_by(id=plot_id).first()

    def create_plot(
        self, storyline_id: int, title: str, description: str | None = None
    ) -> schema.LitographyPlot:
        with Session(self.engine) as session:
            plot = schema.LitographyPlot(
                title=title, description=description, storyline_id=storyline_id
            )
            session.add(plot)
            session.commit()
            session.refresh(plot)
            return plot

    def delete_plot_cascade(self, plot_id: int) -> bool:
        """Delete a plot, its sections, the section↔node links, and any nodes
        that were *only* in those sections. Mirrors what the controller's
        `on_delete_plot_clicked` block did inline."""
        with Session(self.engine) as session:
            plot = session.query(schema.LitographyPlot).filter_by(id=plot_id).first()
            if plot is None:
                return False

            sections = (
                session.query(schema.LitographyPlotSection)
                .filter_by(plot_id=plot_id)
                .all()
            )
            for section in sections:
                # Remove the junction rows first.
                session.query(schema.LitographyNodeToPlotSection).filter_by(
                    litography_plot_section_id=section.id
                ).delete(synchronize_session=False)

                # The original code also deleted nodes whose only section
                # membership was this one. We replicate by deleting any node
                # joined exclusively through this section.
                nodes = (
                    session.query(schema.LitographyNode)
                    .join(
                        schema.LitographyNodeToPlotSection,
                        schema.LitographyNode.id
                        == schema.LitographyNodeToPlotSection.node_id,
                    )
                    .filter(
                        schema.LitographyNodeToPlotSection.litography_plot_section_id
                        == section.id
                    )
                    .all()
                )
                for node in nodes:
                    session.delete(node)

                session.delete(section)

            session.delete(plot)
            session.commit()
            return True

    def get_plot_sections(
        self, plot_id: int
    ) -> list[schema.LitographyPlotSection]:
        """Plot sections ordered by id (matches the controller's existing
        ordering used to build tab indexes)."""
        with Session(self.engine) as session:
            return (
                session.query(schema.LitographyPlotSection)
                .filter_by(plot_id=plot_id)
                .order_by(schema.LitographyPlotSection.id)
                .all()
            )

    def get_plot_section(
        self, section_id: int
    ) -> schema.LitographyPlotSection | None:
        with Session(self.engine) as session:
            return (
                session.query(schema.LitographyPlotSection)
                .filter_by(id=section_id)
                .first()
            )

    def create_plot_section(
        self,
        plot_id: int,
        section_type: schema.PlotSectionType = schema.PlotSectionType.FLAT,
    ) -> schema.LitographyPlotSection:
        with Session(self.engine) as session:
            section = schema.LitographyPlotSection(
                plot_section_type=section_type, plot_id=plot_id
            )
            session.add(section)
            session.commit()
            session.refresh(section)
            return section

    def update_plot_section_type(
        self, section_id: int, section_type: schema.PlotSectionType
    ) -> bool:
        with Session(self.engine) as session:
            section = (
                session.query(schema.LitographyPlotSection)
                .filter_by(id=section_id)
                .first()
            )
            if section is None:
                return False
            section.plot_section_type = section_type
            session.commit()
            return True

    def delete_plot_section(self, section_id: int) -> bool:
        with Session(self.engine) as session:
            section = (
                session.query(schema.LitographyPlotSection)
                .filter_by(id=section_id)
                .first()
            )
            if section is None:
                return False
            session.delete(section)
            session.commit()
            return True

    def get_nodes_in_plot_section(
        self, section_id: int, storyline_id: int
    ) -> list[schema.LitographyNode]:
        with Session(self.engine) as session:
            return (
                session.query(schema.LitographyNode)
                .join(
                    schema.LitographyNodeToPlotSection,
                    schema.LitographyNode.id
                    == schema.LitographyNodeToPlotSection.node_id,
                )
                .filter(
                    schema.LitographyNodeToPlotSection.litography_plot_section_id
                    == section_id,
                    schema.LitographyNode.storyline_id == storyline_id,
                )
                .all()
            )

    def add_node_to_plot_section(self, node_id: int, section_id: int) -> bool:
        """Idempotent: returns True if a new link was created, False if it
        already existed. Both outcomes leave the link in place."""
        with Session(self.engine) as session:
            existing = (
                session.query(schema.LitographyNodeToPlotSection)
                .filter_by(node_id=node_id, litography_plot_section_id=section_id)
                .first()
            )
            if existing is not None:
                return False
            link = schema.LitographyNodeToPlotSection(
                node_id=node_id, litography_plot_section_id=section_id
            )
            session.add(link)
            session.commit()
            return True

    def move_node_to_plot_section(
        self, node_id: int, new_section_id: int
    ) -> None:
        """Remove all current section links for this node and replace with
        a single link to the new section."""
        with Session(self.engine) as session:
            session.query(schema.LitographyNodeToPlotSection).filter_by(
                node_id=node_id
            ).delete(synchronize_session=False)
            session.add(
                schema.LitographyNodeToPlotSection(
                    node_id=node_id, litography_plot_section_id=new_section_id
                )
            )
            session.commit()

    def get_section_for_node(
        self, node_id: int
    ) -> schema.LitographyNodeToPlotSection | None:
        """First section the node belongs to. The schema permits multiple but
        the controller only ever writes one — this helper matches that."""
        with Session(self.engine) as session:
            return (
                session.query(schema.LitographyNodeToPlotSection)
                .filter_by(node_id=node_id)
                .first()
            )

    def get_input_connections_for_node(
        self, node_id: int
    ) -> list[schema.NodeConnection]:
        """Connections where this node is the *input*."""
        with Session(self.engine) as session:
            return (
                session.query(schema.NodeConnection)
                .filter_by(input_node_id=node_id)
                .all()
            )

    def get_output_connections_for_node(
        self, node_id: int
    ) -> list[schema.NodeConnection]:
        """Connections where this node is the *output*."""
        with Session(self.engine) as session:
            return (
                session.query(schema.NodeConnection)
                .filter_by(output_node_id=node_id)
                .all()
            )

    # --- LitographyNotes helpers (Phase 3b) -------------------------------

    def get_notes_for_node(
        self, node_id: int, storyline_id: int
    ) -> list[schema.LitographyNotes]:
        with Session(self.engine) as session:
            return (
                session.query(schema.LitographyNotes)
                .filter_by(linked_node_id=node_id, storyline_id=storyline_id)
                .all()
            )

    def count_notes_for_node(self, node_id: int, storyline_id: int) -> int:
        with Session(self.engine) as session:
            return (
                session.query(schema.LitographyNotes)
                .filter_by(linked_node_id=node_id, storyline_id=storyline_id)
                .count()
            )

    def create_litography_note(
        self,
        node_id: int,
        title: str,
        description: str | None,
        note_type: schema.NoteType,
        storyline_id: int,
    ) -> schema.LitographyNotes:
        with Session(self.engine) as session:
            note = schema.LitographyNotes(
                title=title,
                description=description,
                note_type=note_type,
                linked_node_id=node_id,
                storyline_id=storyline_id,
            )
            session.add(note)
            session.commit()
            session.refresh(note)
            return note

    def update_litography_note(
        self,
        note_id: int,
        storyline_id: int,
        *,
        title: str | None = None,
        description: str | None = None,
        note_type: schema.NoteType | None = None,
    ) -> bool:
        with Session(self.engine) as session:
            note = (
                session.query(schema.LitographyNotes)
                .filter_by(id=note_id, storyline_id=storyline_id)
                .first()
            )
            if note is None:
                return False
            if title is not None:
                note.title = title
            if description is not None:
                note.description = description
            if note_type is not None:
                note.note_type = note_type
            session.commit()
            return True

    def delete_litography_note(self, note_id: int, storyline_id: int) -> bool:
        with Session(self.engine) as session:
            note = (
                session.query(schema.LitographyNotes)
                .filter_by(id=note_id, storyline_id=storyline_id)
                .first()
            )
            if note is None:
                return False
            session.delete(note)
            session.commit()
            return True

    # --- Note ↔ entity association dispatcher ----------------------------
    # The controller exposes string entity_types ("actor", "location", "object",
    # ...). We translate those into ORM classes + foreign-key column names
    # exactly once, here, instead of replicating the if/elif chain at every
    # call site. Adding a new association type means one entry below.

    _NOTE_ASSOCIATION_MAP: dict[str, tuple[type, str]] = {
        "actor": (schema.LitographyNoteToActor, "actor_id"),
        "background": (schema.LitographyNoteToBackground, "background_id"),
        "class": (schema.LitographyNoteToClass, "class_id"),
        "faction": (schema.LitographyNoteToFaction, "faction_id"),
        "history": (schema.LitographyNoteToHistory, "history_id"),
        "location": (schema.LitographyNoteToLocation, "location_id"),
        "object": (schema.LitographyNoteToObject, "object_id"),
        "race": (schema.LitographyNoteToRace, "race_id"),
        "skill": (schema.LitographyNoteToSkills, "skill_id"),
        "sub_race": (schema.LitographyNoteToSubRace, "sub_race_id"),
        "world_data": (schema.LitographyNoteToWorldData, "world_data_id"),
    }

    def get_note_associations(self, note_id: int) -> dict[str, list]:
        """All entity associations for a note, grouped by entity type.

        Keys match the controller's existing dictionary shape (`actors`,
        `backgrounds`, ...) so call sites don't need to change.
        """
        plurals = {
            "actor": "actors",
            "background": "backgrounds",
            "class": "classes",
            "faction": "factions",
            "history": "histories",
            "location": "locations",
            "object": "objects",
            "race": "races",
            "skill": "skills",
            "sub_race": "sub_races",
            "world_data": "world_data",
        }
        out: dict[str, list] = {}
        with Session(self.engine) as session:
            for entity_type, (cls, _) in self._NOTE_ASSOCIATION_MAP.items():
                rows = session.query(cls).filter_by(note_id=note_id).all()
                out[plurals[entity_type]] = rows
        return out

    def create_note_association(
        self, note_id: int, entity_type: str, entity_id: int
    ) -> bool:
        mapping = self._NOTE_ASSOCIATION_MAP.get(entity_type)
        if mapping is None:
            return False
        cls, fk_col = mapping
        with Session(self.engine) as session:
            session.add(cls(**{"note_id": note_id, fk_col: entity_id}))
            session.commit()
            return True

    def delete_note_association(
        self, note_id: int, entity_type: str, entity_id: int
    ) -> bool:
        mapping = self._NOTE_ASSOCIATION_MAP.get(entity_type)
        if mapping is None:
            return False
        cls, fk_col = mapping
        with Session(self.engine) as session:
            row = (
                session.query(cls)
                .filter_by(**{"note_id": note_id, fk_col: entity_id})
                .first()
            )
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True

    # --- Lore entities cross-table fetch (Phase 3b) ------------------------

    def get_lore_entities_for_setting(
        self, setting_id: int
    ) -> dict[str, list]:
        """Return every world-building entity in a setting, grouped by table.

        The shape exactly matches the controller's existing usage so the
        call site is a one-line replacement.
        """
        with Session(self.engine) as session:
            return {
                "actors": session.query(schema.Actor).filter_by(setting_id=setting_id).all(),
                "backgrounds": session.query(schema.Background).filter_by(setting_id=setting_id).all(),
                "classes": session.query(schema.Class_).filter_by(setting_id=setting_id).all(),
                "factions": session.query(schema.Faction).filter_by(setting_id=setting_id).all(),
                "histories": session.query(schema.History).filter_by(setting_id=setting_id).all(),
                "locations": session.query(schema.Location).filter_by(setting_id=setting_id).all(),
                "objects": session.query(schema.Object_).filter_by(setting_id=setting_id).all(),
                "races": session.query(schema.Race).filter_by(setting_id=setting_id).all(),
                "skills": session.query(schema.Skills).filter_by(setting_id=setting_id).all(),
                "sub_races": session.query(schema.SubRace).filter_by(setting_id=setting_id).all(),
                "world_data": session.query(schema.WorldData).filter_by(setting_id=setting_id).all(),
            }

    # --- Cascade node delete (Phase 3b) -----------------------------------

    def delete_node_with_associations(
        self, node_id: int, storyline_id: int
    ) -> bool:
        """Delete a node, its connections, and its notes in one transaction.

        Mirrors the inline cascade in `on_delete_node` and
        `on_delete_node_button_clicked`. Returns True iff the node existed."""
        with Session(self.engine) as session:
            node = (
                session.query(schema.LitographyNode)
                .filter_by(id=node_id, storyline_id=storyline_id)
                .first()
            )
            if node is None:
                return False

            # Connections involving this node (either direction).
            session.query(schema.NodeConnection).filter(
                (schema.NodeConnection.output_node_id == node_id)
                | (schema.NodeConnection.input_node_id == node_id)
            ).delete(synchronize_session=False)

            # Notes pinned to the node.
            session.query(schema.LitographyNotes).filter_by(
                linked_node_id=node_id, storyline_id=storyline_id
            ).delete(synchronize_session=False)

            session.delete(node)
            session.commit()
            return True

    def get_node_in_storyline(
        self, node_id: int, storyline_id: int
    ) -> schema.LitographyNode | None:
        """Used by the controller's existence-check before deleting."""
        with Session(self.engine) as session:
            return (
                session.query(schema.LitographyNode)
                .filter_by(id=node_id, storyline_id=storyline_id)
                .first()
            )

    # --- Storyline ↔ Setting derivation (Phase 3c) ------------------------

    def get_first_setting_id_for_storyline(
        self, storyline_id: int
    ) -> int | None:
        """First (and typically only) setting linked to this storyline. The
        controller calls this when switching storylines, to keep the active
        setting in sync."""
        with Session(self.engine) as session:
            link = (
                session.query(schema.StorylineToSetting)
                .filter_by(storyline_id=storyline_id)
                .first()
            )
            return link.setting_id if link else None

    def get_first_storyline_id_for_setting(self, setting_id: int) -> int | None:
        with Session(self.engine) as session:
            link = (
                session.query(schema.StorylineToSetting)
                .filter_by(setting_id=setting_id)
                .first()
            )
            return link.storyline_id if link else None

    # --- Storyweaver entity search/create/details (Phase 3d) --------------
    # The Storyweaver editor uses prefix-coded ids ("actor_42", "location_7")
    # to disambiguate cross-table references. These helpers centralize that
    # convention so the controller and any future callers don't reinvent it.

    @staticmethod
    def _actor_full_name(actor: schema.Actor) -> str:
        parts = [
            getattr(actor, "first_name", None),
            getattr(actor, "middle_name", None),
            getattr(actor, "last_name", None),
        ]
        joined = " ".join(p for p in parts if p)
        return joined if joined else f"Actor {actor.id}"

    def search_storyweaver_entities(
        self, setting_id: int, query: str | None = None
    ) -> list[dict]:
        """Cross-table substring search across the entities the Storyweaver
        editor links into prose. Returns dicts with prefix-coded ids that
        match the editor's existing payload contract."""
        out: list[dict] = []
        like = f"%{query}%" if query else None
        with Session(self.engine) as session:
            actor_q = session.query(schema.Actor).filter(
                schema.Actor.setting_id == setting_id
            )
            if like:
                actor_q = actor_q.filter(
                    schema.Actor.first_name.ilike(like)
                    | schema.Actor.middle_name.ilike(like)
                    | schema.Actor.last_name.ilike(like)
                )
            for actor in actor_q.all():
                out.append(
                    {
                        "id": f"actor_{actor.id}",
                        "name": self._actor_full_name(actor),
                        "type": "actor",
                    }
                )

            for orm_cls, prefix in (
                (schema.Location, "location"),
                (schema.Faction, "faction"),
                (schema.Object_, "object"),
                (schema.WorldData, "worlddata"),
            ):
                q = session.query(orm_cls).filter(orm_cls.setting_id == setting_id)
                if like:
                    q = q.filter(orm_cls.name.ilike(like))
                for row in q.all():
                    if not row.name:
                        continue
                    out.append(
                        {"id": f"{prefix}_{row.id}", "name": row.name, "type": prefix}
                    )

        out.sort(key=lambda e: e["name"].lower())
        return out

    _STORYWEAVER_CREATE_MAP: dict[str, type] = {
        "location": schema.Location,
        "faction": schema.Faction,
        "object": schema.Object_,
        "worlddata": schema.WorldData,
    }

    def create_storyweaver_entity(
        self, entity_type: str, entity_name: str, setting_id: int
    ) -> str | None:
        """Create a new entity from the Storyweaver "+" affordance.

        Returns the prefix-coded id (`"actor_42"`) or None if the type is
        unknown. Actor names are split on whitespace: last word is `last_name`,
        everything before is `first_name` (single-word names go to `first_name`).
        """
        with Session(self.engine) as session:
            if entity_type == "actor":
                parts = entity_name.strip().split()
                first_name = parts[0] if len(parts) == 1 else " ".join(parts[:-1])
                last_name = "" if len(parts) == 1 else parts[-1]
                actor = schema.Actor(
                    first_name=first_name, last_name=last_name, setting_id=setting_id
                )
                session.add(actor)
                session.commit()
                session.refresh(actor)
                return f"actor_{actor.id}"

            cls = self._STORYWEAVER_CREATE_MAP.get(entity_type)
            if cls is None:
                return None
            row = cls(name=entity_name, setting_id=setting_id)
            session.add(row)
            session.commit()
            session.refresh(row)
            return f"{entity_type}_{row.id}"

    def get_storyweaver_entity_details(
        self, entity_type: str, entity_id: int
    ) -> tuple[str, str] | None:
        """Resolve a hover request to (display name, formatted detail blob).

        Returns None if the entity isn't found. Format here matches what the
        controller's old inline code produced — easier to keep parity than to
        change both sides at once.
        """
        with Session(self.engine) as session:
            if entity_type in {"character", "actor"}:
                actor = session.query(schema.Actor).filter_by(id=entity_id).first()
                if actor is None:
                    return None
                name = self._actor_full_name(actor)
                detail_lines: list[str] = []
                if actor.title:
                    detail_lines.append(f"Title: {actor.title}")
                if actor.actor_role:
                    detail_lines.append(f"Role: {actor.actor_role}")
                if actor.actor_age:
                    detail_lines.append(f"Age: {actor.actor_age}")
                if actor.job:
                    detail_lines.append(f"Occupation: {actor.job}")
                if actor.appearance:
                    snippet = (
                        f"\n{actor.appearance[:150]}..."
                        if len(actor.appearance) > 150
                        else f"\n{actor.appearance}"
                    )
                    detail_lines.append(snippet)
                return name, "\n".join(detail_lines) if detail_lines else "No additional details available."

            if entity_type == "location":
                row = session.query(schema.Location).filter_by(id=entity_id).first()
                if row is None:
                    return None
                name = row.name or f"Location {row.id}"
                lines: list[str] = []
                if getattr(row, "location_type", None):
                    lines.append(f"Type: {row.location_type}")
                if row.description:
                    lines.append(_truncate_block(row.description, 150))
                return name, "\n".join(lines) if lines else "No additional details available."

            if entity_type == "faction":
                row = session.query(schema.Faction).filter_by(id=entity_id).first()
                if row is None:
                    return None
                name = row.name or f"Faction {row.id}"
                lines = []
                if row.description:
                    lines.append(_truncate(row.description, 150))
                if getattr(row, "goals", None):
                    lines.append(f"Goals: {_truncate(row.goals, 100)}")
                return name, "\n".join(lines) if lines else "No additional details available."

            if entity_type == "object":
                row = session.query(schema.Object_).filter_by(id=entity_id).first()
                if row is None:
                    return None
                name = row.name or f"Object {row.id}"
                lines = []
                if row.description:
                    lines.append(_truncate(row.description, 150))
                if getattr(row, "rarity", None):
                    lines.append(f"Rarity: {row.rarity}")
                if getattr(row, "object_value", None):
                    lines.append(f"Value: {row.object_value}")
                return name, "\n".join(lines) if lines else "No additional details available."

            if entity_type == "worlddata":
                row = session.query(schema.WorldData).filter_by(id=entity_id).first()
                if row is None:
                    return None
                name = row.name or f"World Data {row.id}"
                lines = []
                if row.description:
                    lines.append(_truncate(row.description, 150))
                return name, "\n".join(lines) if lines else "No additional details available."

            return None
