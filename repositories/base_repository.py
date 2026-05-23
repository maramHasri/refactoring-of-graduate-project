from utils.db import db


class BaseRepository:
    def commit(self):
        db.session.commit()

    def rollback(self):
        db.session.rollback()

    def flush(self):
        db.session.flush()

    def add(self, entity):
        db.session.add(entity)
        return entity
