from __future__ import annotations

from stac_scout.models import Manifest


def odc_stac_recipe(manifest: Manifest) -> str:
    request = manifest.request
    geometry = repr(request.geometry)
    assets = repr(list(manifest.asset_keys))
    resolution = repr(request.max_spatial_resolution_m)
    interval = f"{request.datetime.start.isoformat()}/{request.datetime.end.isoformat()}"

    return f'''from odc.geo import Geometry
import odc.stac
from pystac_client import Client

catalog = Client.open({manifest.catalog_url!r})
aoi_geojson = {geometry}
aoi = Geometry(aoi_geojson, crs="EPSG:4326")
search = catalog.search(
    collections=[{manifest.collection_id!r}],
    intersects=aoi_geojson,
    datetime={interval!r},
)
items = list(search.items())

ds = odc.stac.load(
    items,
    bands={assets},
    geopolygon=aoi,
    resolution={resolution},
)
'''
