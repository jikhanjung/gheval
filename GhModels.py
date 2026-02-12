import datetime
from peewee import (
    SqliteDatabase, Model, CharField, TextField, DoubleField,
    IntegerField, DateTimeField, ForeignKeyField,
)

db = SqliteDatabase(None)


class BaseModel(Model):
    class Meta:
        database = db


class GeoHeritageSite(BaseModel):
    site_name = CharField()
    site_desc = TextField(null=True)
    latitude = DoubleField()
    longitude = DoubleField()
    address = CharField(null=True)
    site_type = CharField(null=True)
    created_at = DateTimeField(default=datetime.datetime.now)
    updated_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "geoheritage_site"

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.now()
        return super().save(*args, **kwargs)


class SiteScreenshot(BaseModel):
    site = ForeignKeyField(GeoHeritageSite, backref="screenshots", on_delete="CASCADE")
    file_path = CharField()
    map_type = CharField(default="HYBRID")
    zoom_level = IntegerField(default=15)
    scale_info = CharField(null=True)
    captured_at = DateTimeField(default=datetime.datetime.now)
    note = TextField(null=True)

    class Meta:
        table_name = "site_screenshot"


class RiskEvaluation(BaseModel):
    site = ForeignKeyField(GeoHeritageSite, backref="evaluations", on_delete="CASCADE")
    screenshot = ForeignKeyField(SiteScreenshot, backref="evaluations", on_delete="SET NULL", null=True)
    road_proximity = IntegerField(default=1)
    road_distance = DoubleField(null=True)
    road_snap_lat = DoubleField(null=True)
    road_snap_lng = DoubleField(null=True)
    accessibility = IntegerField(default=1)
    vegetation_cover = IntegerField(default=1)
    development_signs = IntegerField(default=1)
    overall_risk = IntegerField(default=4)
    risk_level = CharField(default="LOW")
    evaluator_notes = TextField(null=True)
    evaluated_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "risk_evaluation"


class SitePhoto(BaseModel):
    site = ForeignKeyField(GeoHeritageSite, backref="photos", on_delete="CASCADE")
    file_path = CharField()
    photo_type = CharField(null=True)
    description = TextField(null=True)
    taken_at = DateTimeField(null=True)
    created_at = DateTimeField(default=datetime.datetime.now)

    class Meta:
        table_name = "site_photo"


ALL_MODELS = [GeoHeritageSite, SiteScreenshot, RiskEvaluation, SitePhoto]


def initialize_db(db_path):
    """Initialize the database at the given path."""
    db.init(db_path)
    db.connect()
    db.create_tables(ALL_MODELS)
    return db
