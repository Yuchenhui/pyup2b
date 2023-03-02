#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# @Author:      thepoy
# @Email:       thepoy@163.com
# @File Name:   cache.py
# @Created At:  2023-02-28 22:16:22
# @Modified At: 2023-03-02 23:43:22
# @Modified By: thepoy

import sqlite3
import hashlib

from up2b.up2b_lib.constants import CACHE_DATABASE, PYTHON_VERSION

if PYTHON_VERSION >= (3, 9):
    from functools import cache
else:
    from functools import lru_cache

    cache = lru_cache(maxsize=None)

from typing import Any, Optional, Tuple, Union
from pathlib import Path
from up2b.up2b_lib.log import child_logger


logger = child_logger(__name__)


@cache
def file_md5(filepath: Path) -> str:
    h = hashlib.md5()

    with filepath.open("rb") as f:
        while True:
            data = f.read(1024)
            if not data:
                break

            h.update(data)

    return h.hexdigest()


URL = str
MD5 = str


class Cache:
    def __init__(self) -> None:
        self.conn = sqlite3.connect(CACHE_DATABASE)

        self.create_table()

    def create_table(self):
        c = self.conn.cursor()
        sql = """
        CREATE TABLE IF NOT EXISTS cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
            hash CHAR(128) NOT NULL,
            image_bed TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE
        );
        """
        c.execute(sql)
        sql = """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_hash_ib
                ON cache (hash, image_bed);
        """
        c.execute(sql)
        self.commit()

    @cache
    def is_exists(self, md5: str, image_bed: Optional[str] = None) -> Optional[str]:
        if image_bed:
            sql = """
                SELECT url FROM cache
                WHERE hash = ? AND image_bed = ?;
            """

            c = self.execute(sql, md5, image_bed)
        else:
            sql = """
                SELECT url FROM cache WHERE hash = ?;
            """

            c = self.execute(sql, md5)

        result = c.fetchone()
        if not result:
            return None

        return result[0]

    @cache
    def chech_cache_of_image_bed(
        self, filepath: Path, image_bed: str
    ) -> Union[Tuple[URL, None], Tuple[None, MD5]]:
        """精准查询指定图床中是否缓存过图片

        :param filepath: 图片真实路径或缓存路径
        :type filepath: Path
        :param image_bed: 图床名
        :type image_bed: str
        :returns: 缓存的图片链接或文件 md5
        :rtype: {Union[Tuple[URL, None], Tuple[None, MD5]]}
        """

        md5 = file_md5(filepath)

        logger.debug("md5: '%s' -> '%s'", filepath, md5)

        url = self.is_exists(md5, image_bed)
        if url:
            return (url, None)

        return (None, md5)

    @cache
    def chech_cache(self, filepath: Path) -> Union[Tuple[URL, None], Tuple[None, MD5]]:
        """模糊查询图片缓存。

        不论任何在图床中上传过图片，只要查询到即返回已上传的图片链接。
        :param filepath: 图片真实路径或缓存路径
        :type filepath: Path
        :returns: 缓存的图片链接或文件 md5
        :rtype: {Union[Tuple[URL, None], Tuple[None, MD5]]}
        """

        md5 = file_md5(filepath)

        logger.debug("%s md5: %s", filepath, md5)

        url = self.is_exists(md5)
        if url:
            return (url, None)

        return (None, md5)

    def save(self, md5: str, image_bed: str, url: str, force: bool = False):
        exists = self.is_exists(md5, image_bed)

        if exists:
            if force:
                sql = """
                    UPDATE cache SET url = ? WHERE hash = ? AND image_bed = ?;
                """

                return self.execute(sql, url, md5, image_bed)

            logger.warning("图片已存在且未开启强制更新，图片链接不会保存")
        else:
            sql = """
                INSERT INTO cache (url, hash, image_bed) VALUES (?, ?, ?);
            """

            return self.execute(sql, url, md5, image_bed)

    def execute(self, sql: str, *params: Any):
        c = self.conn.cursor()
        return c.execute(sql, params)

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

    def __del__(self):
        self.commit()
        self.close()
