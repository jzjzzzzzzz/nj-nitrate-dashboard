from pathlib import Path
import json
import math

from flask import Flask, render_template, jsonify, send_from_directory, abort


app = Flask(__name__)


BASE_DIR = Path(__file__).resolve().parent

DASHBOARD_DIR = BASE_DIR / "output" / "dashboard"
MAPS_DIR = BASE_DIR / "output" / "maps"
FIGURES_DIR = BASE_DIR / "output" / "figures"
PROPOSAL_DIR = BASE_DIR / "output" / "proposal"


def existing_child_file(base_dir, filename, allowed_suffixes=None):
    base_path = base_dir.resolve()
    candidate = (base_path / filename).resolve()

    try:
        candidate.relative_to(base_path)
    except ValueError:
        return None

    if allowed_suffixes is not None and candidate.suffix.lower() not in allowed_suffixes:
        return None

    if not candidate.is_file():
        return None

    return candidate


def read_json_file(path):
    if not path.exists():
        return None

    with open(path, "r", encoding="utf-8") as f:
        return clean_json_value(json.load(f))


def clean_json_value(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, list):
        return [clean_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: clean_json_value(item) for key, item in value.items()}
    return value


@app.route("/")
@app.route("/index.html")
def index():
    return render_template("index.html")


@app.route("/watersheds")
@app.route("/watersheds.html")
def watersheds():
    return render_template("watersheds.html")


@app.route("/proposal")
@app.route("/proposal.html")
def proposal():
    return render_template("proposal.html")


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.route("/__routes")
def route_inventory():
    return jsonify(sorted(str(rule) for rule in app.url_map.iter_rules()))


@app.route("/api/summary")
def api_summary():
    path = DASHBOARD_DIR / "summary_cards.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({"error": "summary_cards.json not found"}), 404

    return jsonify(data)


@app.route("/api/seasonal-chart")
def api_seasonal_chart():
    path = DASHBOARD_DIR / "seasonal_chart.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({"error": "seasonal_chart.json not found"}), 404

    return jsonify(data)


@app.route("/api/monthly-chart")
def api_monthly_chart():
    path = DASHBOARD_DIR / "monthly_chart.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({"error": "monthly_chart.json not found"}), 404

    return jsonify(data)


@app.route("/api/yearly-trend")
def api_yearly_trend():
    path = DASHBOARD_DIR / "yearly_trend_chart.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({"error": "yearly_trend_chart.json not found"}), 404

    return jsonify(data)


@app.route("/api/monthly-moving-average")
def api_monthly_moving_average():
    path = DASHBOARD_DIR / "monthly_moving_average_chart.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({"error": "monthly_moving_average_chart.json not found"}), 404

    return jsonify(data)


@app.route("/api/hotspot-moving-average")
def api_hotspot_moving_average():
    path = DASHBOARD_DIR / "hotspot_moving_average_chart.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({"error": "hotspot_moving_average_chart.json not found"}), 404

    return jsonify(data)


@app.route("/api/station-index")
def api_station_index():
    path = DASHBOARD_DIR / "station_detail_index.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({"error": "station_detail_index.json not found"}), 404

    return jsonify(data)


@app.route("/api/station-detail/<path:filename>")
def api_station_detail(filename):
    station_dir = DASHBOARD_DIR / "station_details"
    path = existing_child_file(station_dir, filename, {".json"})

    if path is None:
        return jsonify({"error": f"{filename} not found"}), 404

    data = read_json_file(path)

    if data is None:
        return jsonify({"error": f"{filename} could not be loaded"}), 500

    return jsonify(data)


@app.route("/api/watershed-summary")
def api_watershed_summary():
    path = DASHBOARD_DIR / "watershed_summary.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({"error": "watershed_summary.json not found"}), 404

    return jsonify(data)


@app.route("/api/watershed-land-use")
def api_watershed_land_use():
    path = DASHBOARD_DIR / "watershed_land_use_nitrate_joined.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({"error": "watershed_land_use_nitrate_joined.json not found"}), 404

    return jsonify(data)


@app.route("/api/land-use-correlation")
def api_land_use_correlation():
    path = DASHBOARD_DIR / "land_use_nitrate_correlation.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "land_use_nitrate_correlation.json not found. Please run Step 11 first."
        }), 404

    return jsonify(data)


@app.route("/api/land-use-ranking")
def api_land_use_ranking():
    path = DASHBOARD_DIR / "land_use_nitrate_ranking.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "land_use_nitrate_ranking.json not found. Please run Step 11 first."
        }), 404

    return jsonify(data)


@app.route("/api/facility-nitrate-correlation")
def api_facility_nitrate_correlation():
    path = DASHBOARD_DIR / "facility_nitrate_correlation.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "facility_nitrate_correlation.json not found. Please run Step 13 first."
        }), 404

    return jsonify(data)


@app.route("/api/facility-nitrate-ranking")
def api_facility_nitrate_ranking():
    path = DASHBOARD_DIR / "facility_nitrate_ranking.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "facility_nitrate_ranking.json not found. Please run Step 13 first."
        }), 404

    return jsonify(data)


@app.route("/api/multivariable-model-comparison")
def api_multivariable_model_comparison():
    path = DASHBOARD_DIR / "multivariable_model_comparison.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "multivariable_model_comparison.json not found. Please run Step 15 first."
        }), 404

    return jsonify(data)


@app.route("/api/multivariable-model-coefficients")
def api_multivariable_model_coefficients():
    path = DASHBOARD_DIR / "multivariable_model_coefficients.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "multivariable_model_coefficients.json not found. Please run Step 15 first."
        }), 404

    return jsonify(data)


@app.route("/api/multivariable-model-predictions")
def api_multivariable_model_predictions():
    path = DASHBOARD_DIR / "multivariable_model_predictions.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "multivariable_model_predictions.json not found. Please run Step 15 first."
        }), 404

    return jsonify(data)


@app.route("/api/multivariable-model-vif")
def api_multivariable_model_vif():
    path = DASHBOARD_DIR / "multivariable_model_vif.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "multivariable_model_vif.json not found. Please run Step 15 first."
        }), 404

    return jsonify(data)


@app.route("/api/research-proposal-summary")
def api_research_proposal_summary():
    path = DASHBOARD_DIR / "research_proposal_summary.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "research_proposal_summary.json not found. Please run Step 17 first."
        }), 404

    return jsonify(data)


@app.route("/api/hotspot-threshold-robustness")
def api_hotspot_threshold_robustness():
    path = DASHBOARD_DIR / "hotspot_threshold_robustness.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "hotspot_threshold_robustness.json not found. Please run Step 18 first."
        }), 404

    return jsonify(data)


@app.route("/api/confidence-weighted-watershed")
def api_confidence_weighted_watershed():
    path = DASHBOARD_DIR / "confidence_weighted_watershed_summary.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "confidence_weighted_watershed_summary.json not found. Please run Step 18 first."
        }), 404

    return jsonify(data)


@app.route("/api/simplified-model-vif-comparison")
def api_simplified_model_vif_comparison():
    path = DASHBOARD_DIR / "simplified_model_vif_comparison.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "simplified_model_vif_comparison.json not found. Please run Step 18 first."
        }), 404

    return jsonify(data)


@app.route("/api/rainfall-nitrate-correlation")
def api_rainfall_nitrate_correlation():
    path = DASHBOARD_DIR / "rainfall_nitrate_yearly_correlation.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "rainfall_nitrate_yearly_correlation.json not found. Please run Step 18 first."
        }), 404

    return jsonify(data)


@app.route("/api/station-buffer-land-use-correlation")
def api_station_buffer_land_use_correlation():
    path = DASHBOARD_DIR / "station_buffer_land_use_correlation.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "station_buffer_land_use_correlation.json not found. Please run Step 19 first."
        }), 404

    return jsonify(data)


@app.route("/api/additional-factor-correlation")
def api_additional_factor_correlation():
    path = DASHBOARD_DIR / "additional_factor_nitrate_correlation.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "additional_factor_nitrate_correlation.json not found. Please run Step 20 first."
        }), 404

    return jsonify(data)


@app.route("/api/additional-factor-model-comparison")
def api_additional_factor_model_comparison():
    path = DASHBOARD_DIR / "additional_factor_model_comparison.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "additional_factor_model_comparison.json not found. Please run Step 20 first."
        }), 404

    return jsonify(data)


@app.route("/api/discharge-volume-status")
def api_discharge_volume_status():
    path = DASHBOARD_DIR / "discharge_volume_status.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "discharge_volume_status.json not found. Please run Step 20 first."
        }), 404

    return jsonify(data)


@app.route("/api/discharge-permit-match-summary")
def api_discharge_permit_match_summary():
    path = DASHBOARD_DIR / "discharge_permit_match_summary.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "discharge_permit_match_summary.json not found. Please run Step 20 first."
        }), 404

    return jsonify(data)


@app.route("/api/hydrography-outfall-status")
def api_hydrography_outfall_status():
    path = DASHBOARD_DIR / "hydrography_outfall_status.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "hydrography_outfall_status.json not found. Please run Step 21 first."
        }), 404

    return jsonify(data)


@app.route("/api/watershed-outfall-feature-summary")
def api_watershed_outfall_feature_summary():
    path = DASHBOARD_DIR / "watershed_outfall_feature_summary.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "watershed_outfall_feature_summary.json not found. Please run Step 21 first."
        }), 404

    return jsonify(data)


@app.route("/api/watershed-hydrography-flowline-summary")
def api_watershed_hydrography_flowline_summary():
    path = DASHBOARD_DIR / "watershed_hydrography_flowline_summary.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "watershed_hydrography_flowline_summary.json not found. Please run Step 21 first."
        }), 404

    return jsonify(data)


@app.route("/api/dmr-outfall-snapped-proxies")
def api_dmr_outfall_snapped_proxies():
    path = DASHBOARD_DIR / "dmr_outfall_snapped_proxy_points.json"
    data = read_json_file(path)

    if data is None:
        return jsonify({
            "error": "dmr_outfall_snapped_proxy_points.json not found. Please run Step 21 first."
        }), 404

    return jsonify(data)


@app.route("/maps/<path:filename>")
def serve_map(filename):
    path = existing_child_file(MAPS_DIR, filename, {".html"})

    if path is None:
        abort(404)

    return send_from_directory(MAPS_DIR, filename)


@app.route("/figures/<path:filename>")
def serve_figure(filename):
    path = existing_child_file(FIGURES_DIR, filename, {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"})

    if path is None:
        abort(404)

    return send_from_directory(FIGURES_DIR, filename)


@app.route("/proposal-output/<path:filename>")
def serve_proposal_output(filename):
    path = existing_child_file(PROPOSAL_DIR, filename, {".html", ".md", ".pdf"})

    if path is None:
        abort(404)

    return send_from_directory(PROPOSAL_DIR, filename)


if __name__ == "__main__":
    app.run(debug=True)
