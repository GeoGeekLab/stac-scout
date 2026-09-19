from __future__ import annotations

from stac_scout.models import AssetSigning, Manifest


def odc_stac_recipe(manifest: Manifest) -> str:
    if manifest.asset_signing is AssetSigning.PROVIDER_DEPENDENT:
        raise ValueError("provider-dependent asset signing cannot be rendered generically")

    request = manifest.request
    geometry = repr(request.geometry)
    assets = repr(list(manifest.asset_keys))
    resolution = repr(request.max_spatial_resolution_m)
    interval = f"{request.datetime.start.isoformat()}/{request.datetime.end.isoformat()}"

    if manifest.asset_signing is AssetSigning.PLANETARY_COMPUTER:
        signing_import = "import planetary_computer\n"
        client = (
            f"Client.open({manifest.catalog_url!r}, "
            "modifier=planetary_computer.sign_inplace)"
        )
    else:
        signing_import = ""
        client = f"Client.open({manifest.catalog_url!r})"

    return f"""from odc.geo import Geometry
import odc.stac
{signing_import}from pystac_client import Client

catalog = {client}
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
"""
