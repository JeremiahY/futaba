#
# sql/models/navi.py
#
# futaba - A Discord Mod bot for the Programming server
# Copyright (c) 2017-2018 Jake Richardson, Ammon Smith, jackylam5
#
# futaba is available free of charge under the terms of the MIT
# License. You are free to redistribute and/or modify it under those
# terms. It is distributed in the hopes that it will be useful, but
# WITHOUT ANY WARRANTY. See the LICENSE file for more details.
#

"""
Model for storing tasks scheduled in navi, futaba's temporal assistant.
"""

# False positive when using SQLAlchemy decorators
# pylint: disable=no-value-for-parameter

import functools
import logging

from sqlalchemy import and_, or_
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    Integer,
    Interval,
    JSON,
    Table,
    Unicode,
)
from sqlalchemy import ForeignKey, Sequence
from sqlalchemy.sql import select

from futaba.enums import TaskType
from ..hooks import register_hook

Column = functools.partial(Column, nullable=False)
logger = logging.getLogger(__name__)

__all__ = ["NaviModel", "NaviTaskStorage"]


class NaviTaskStorage:
    __slots__ = (
        "id",
        "guild_id",
        "user_id",
        "timestamp",
        "recurrence",
        "task_type",
        "parameters",
    )

    def __init__(
        self, id, guild_id, user_id, timestamp, recurrence, task_type, parameters
    ):
        self.id = id
        self.guild_id = guild_id
        self.user_id = user_id
        self.timestamp = timestamp
        self.recurrence = recurrence
        self.task_type = task_type
        self.parameters = parameters


class NaviModel:
    __slots__ = ("sql", "tb_tasks")

    def __init__(self, sql, meta):
        self.sql = sql
        self.tb_tasks = Table(
            "tasks",
            meta,
            Column(
                "task_id",
                Integer,
                Sequence("task_seq", metadata=meta),
                primary_key=True,
            ),
            Column("guild_id", BigInteger, ForeignKey("guilds.guild_id")),
            Column("user_id", BigInteger),
            Column("start_timestamp", DateTime),
            Column("recurrence", Interval, nullable=True),
            Column("type", Enum(TaskType)),
            Column("parameters", JSON),
        )

        register_hook("on_guild_leave", self.remove_all_tasks)

    def remove_all_tasks(self, guild):
        logger.info("Removing all tasks in guild '%s' (%d)", guild.name, guild.id)
        delet = self.tb_tasks.delete().where(self.tb_tasks.c.guild_id == guild.id)
        self.sql.execute(delet)

    def get_tasks(self, guild):
        logger.info("Getting all tasks for guild '%s' (%d)", guild.name, guild.id)
        sel = select(
            [
                self.tb_tasks.c.task_id,
                self.tb_tasks.c.user_id,
                self.tb_tasks.c.start_timestamp,
                self.tb_tasks.c.recurrence,
                self.tb_tasks.c.type,
                self.tb_tasks.c.parameters,
            ]
        ).where(self.tb_tasks.c.guild_id == guild.id)
        result = self.sql.execute(sel)

        tasks = {}
        for (
            task_id,
            user_id,
            timestamp,
            recurrence,
            task_type,
            parameters,
        ) in result.fetchall():
            logger.debug(
                "Got navi task %d: %s (%s) by user %d: %s (%s)",
                task_id,
                timestamp,
                recurrence,
                user_id,
                task_type,
                parameters,
            )
            tasks[task_id] = NaviTaskStorage(
                task_id, guild.id, user_id, timestamp, recurrence, task_type, parameters
            )
        return tasks

    def add_task(self, guild, task):
        logger.info(
            "Adding new task id %d for guild '%s' (%d)", task.id, guild.name, guild.id
        )
        ins = self.tb_tasks.insert().values(
            guild_id=guild.id,
            user_id=task.causer.id,
            timestamp=task.timestamp,
            recurrence=task.recurrence,
            task_type=task.type,
            parameters=task.build_parameters(),
        )
        self.sql.execute(ins)

    def remove_task(self, guild, task):
        logger.info(
            "Deleting task id %d from guild '%s' (%d)", task.id, guild.name, guild.id
        )
        delet = self.tb_tasks.delete().where(
            and_(
                self.tb_tasks.c.guild_id == guild.id, self.tb_tasks.c.task_id == task.id
            )
        )
        self.sql.execute(delet)
