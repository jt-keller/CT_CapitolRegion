from pathlib import Path
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

import folium
from folium.plugins import MeasureControl
import geopandas as gpd
import pandas as pd
from branca.colormap import LinearColormap
from matplotlib import colors
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


def add_side_panel(html_path: Path) -> None:
    side_panel_markup = """
    <style>
      #softsite-info-panel {
        position: absolute;
        inset: 0 auto 0 0;
        width: 25%;
        height: 100%;
        z-index: 9999;
        box-sizing: border-box;
        overflow: auto;
        background: #ffffff;
        border-right: 1px solid #d4d4d4;
        color: #1f2933;
        font-family: Arial, Helvetica, sans-serif;
      }

      #softsite-info-panel .panel-header {
        position: sticky;
        top: 0;
        z-index: 1;
        padding: 12px 14px;
        border-bottom: 1px solid #d4d4d4;
        background: #f7f7f7;
      }

      #softsite-info-panel h2 {
        margin: 0;
        font-size: 16px;
        font-weight: 700;
      }

      #softsite-info-panel .panel-subtitle {
        margin-top: 4px;
        font-size: 12px;
        color: #5b6570;
      }

      #softsite-info-panel table {
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
        font-size: 12px;
      }

      #softsite-info-panel th,
      #softsite-info-panel td {
        padding: 7px 10px;
        border-bottom: 1px solid #ececec;
        text-align: left;
        vertical-align: top;
        word-break: break-word;
      }

      #softsite-info-panel th {
        width: 42%;
        color: #4b5563;
        font-weight: 700;
        background: #fbfbfb;
      }

      #softsite-info-empty {
        padding: 14px;
        font-size: 13px;
        color: #5b6570;
      }

      .folium-map {
        left: 25% !important;
        width: 75% !important;
      }

      @media (max-width: 800px) {
        #softsite-info-panel {
          width: 35%;
        }

        .folium-map {
          left: 35% !important;
          width: 65% !important;
        }
      }
    </style>
    <div id="softsite-info-panel">
      <div class="panel-header">
        <h2>Parcel Details</h2>
        <div class="panel-subtitle">Hover or click a parcel</div>
      </div>
      <div id="softsite-info-empty">No parcel selected.</div>
      <table id="softsite-info-table" style="display: none;">
        <tbody></tbody>
      </table>
    </div>
    <script>
      (function () {
        const hiddenFields = new Set(["tot_score_color"]);
        const table = document.querySelector("#softsite-info-table");
        const tbody = table.querySelector("tbody");
        const empty = document.querySelector("#softsite-info-empty");

        function formatValue(value) {
          if (value === null || value === undefined || value === "") {
            return "";
          }
          if (typeof value === "number") {
            return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 3 });
          }
          return String(value);
        }

        function showProperties(properties) {
          tbody.innerHTML = "";
          Object.entries(properties)
            .filter(([key]) => !hiddenFields.has(key))
            .forEach(([key, value]) => {
              const row = document.createElement("tr");
              const label = document.createElement("th");
              const cell = document.createElement("td");
              label.textContent = key;
              cell.textContent = formatValue(value);
              row.append(label, cell);
              tbody.appendChild(row);
            });
          empty.style.display = "none";
          table.style.display = "table";
        }

        function wireLayer(layer) {
          if (layer.feature && layer.feature.properties && layer.on) {
            layer.on({
              mouseover: function () {
                showProperties(layer.feature.properties);
              },
              click: function () {
                showProperties(layer.feature.properties);
              }
            });
          }

          if (layer.eachLayer) {
            layer.eachLayer(wireLayer);
          }
        }

        function findMaps() {
          return Array.from(document.querySelectorAll(".folium-map"))
            .map((element) => window[element.id])
            .filter((value) => value instanceof L.Map);
        }

        window.addEventListener("load", function () {
          findMaps().forEach((map) => {
            map.eachLayer(wireLayer);
            setTimeout(function () {
              map.invalidateSize();
            }, 100);
          });
        });
      })();
    </script>
    """

    html = html_path.read_text()
    html = html.replace("</body>", f"{side_panel_markup}\n</body>")
    html_path.write_text(html)


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

    map_gdf = merged.copy()
    tot_score_values = pd.to_numeric(map_gdf["tot_score"], errors="coerce")
    tot_score_min = tot_score_values.min()
    tot_score_max = tot_score_values.max()
    tot_score_cmap = LinearSegmentedColormap.from_list(
        "tot_score_light_gray_to_hot_pink",
        ["#d9d9d9", "#ff1493"],
    )

    def tot_score_color(value: float) -> str:
        if pd.isna(value):
            return "#777777"
        if tot_score_max == tot_score_min:
            return colors.to_hex(tot_score_cmap(1))
        normalized = (value - tot_score_min) / (tot_score_max - tot_score_min)
        return colors.to_hex(tot_score_cmap(normalized))

    map_gdf["tot_score_color"] = tot_score_values.map(tot_score_color)
    display_columns = list(merged.columns.drop(merged.geometry.name))
    map_html = map_gdf.explore(
        name="Merged Soft Sites",
        color="tot_score_color",
        tiles=GOOGLE_SATELLITE_TILES,
        attr=GOOGLE_ATTRIBUTION,
        legend=False,
        tooltip=False,
        popup=False,
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
    LinearColormap(
        colors=["#d9d9d9", "#ff1493"],
        vmin=tot_score_min,
        vmax=tot_score_max,
        caption="tot_score",
    ).add_to(map_html)
    MeasureControl(
        position="topright",
        primary_length_unit="feet",
        secondary_length_unit="miles",
        primary_area_unit="sqfeet",
        secondary_area_unit="acres",
    ).add_to(map_html)
    folium.LayerControl(collapsed=False).add_to(map_html)
    map_html.save(OUTPUT_HTML)
    add_side_panel(OUTPUT_HTML)
    print(f"Saved map to {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
