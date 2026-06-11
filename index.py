from pathlib import Path
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import geopandas as gpd
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap


INPUT_GPKGS = [
    Path("WestHartford_softsite_result.gpkg"),
    Path("NewBritain_softsite_result.gpkg"),
]
OUTPUT_GPKG = Path("merged_softsite_result.gpkg")
OUTPUT_LAYER = "softsite_result_merged"
OUTPUT_HTML = Path("index.html")
GOOGLE_SATELLITE_TILES = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
GOOGLE_ATTRIBUTION = "Google Satellite"
BASE_OUTPUT_COLUMNS = [
    "location",
    "owner",
    "co_owner",
    "assessed_total",
    "assessed_land",
    "assessed_building",
    "land_acres",
    "zone",
    "state_use_description",
    "occupancy",
    "FAR",
    "area",
]


def read_single_layer(gpkg_path: Path) -> gpd.GeoDataFrame:
    layers = gpd.list_layers(gpkg_path)

    if len(layers) != 1:
        layer_names = ", ".join(layers["name"].astype(str))
        raise ValueError(f"{gpkg_path} has {len(layers)} layers: {layer_names}")

    layer_name = layers.iloc[0]["name"]
    gdf = gpd.read_file(gpkg_path, layer=layer_name)
    gdf = gdf.rename(columns={"FAR_sum": "FAR"})
    print(f"{gpkg_path.name}::{layer_name} fields: {', '.join(gdf.columns)}")
    return gdf


def main() -> None:
    frames = [read_single_layer(gpkg_path) for gpkg_path in INPUT_GPKGS]

    target_crs = frames[0].crs
    aligned_frames = [
        frame.to_crs(target_crs) if frame.crs != target_crs else frame
        for frame in frames
    ]

    merged = gpd.GeoDataFrame(
        pd.concat(aligned_frames, ignore_index=True, sort=False),
        geometry=aligned_frames[0].geometry.name,
        crs=target_crs,
    )
    score_columns = [column for column in merged.columns if column.endswith("_score")]
    output_columns = BASE_OUTPUT_COLUMNS + score_columns + [merged.geometry.name]
    merged = merged[output_columns]

    merged.to_file(OUTPUT_GPKG, layer=OUTPUT_LAYER, driver="GPKG")
    print(f"Merged {len(merged)} features into {OUTPUT_GPKG}::{OUTPUT_LAYER}")
    print(f"Merged fields: {', '.join(merged.columns)}")

    tot_score_values = pd.to_numeric(merged["tot_score"], errors="coerce")
    tot_score_cmap = LinearSegmentedColormap.from_list(
        "tot_score_light_gray_to_hot_pink",
        ["#d9d9d9", "#ff1493"],
    )
    map_html = merged.explore(
        column="tot_score",
        cmap=tot_score_cmap,
        vmin=tot_score_values.min(),
        vmax=tot_score_values.max(),
        tiles=GOOGLE_SATELLITE_TILES,
        attr=GOOGLE_ATTRIBUTION,
        legend=True,
        tooltip=list(merged.columns.drop(merged.geometry.name)),
        popup=True,
        style_kwds={
            "fillOpacity": 0.65,
            "color": "#333333",
            "weight": 0.5,
        },
        missing_kwds={
            "color": "#777777",
            "fillColor": "#777777",
            "fillOpacity": 0.25,
            "label": "Missing tot_score",
        },
    )
    map_html.save(OUTPUT_HTML)
    print(f"Saved map to {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
