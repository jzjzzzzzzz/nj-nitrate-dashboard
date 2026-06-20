# water_analysis 工作与结果汇总

生成日期：2026-06-18  
项目目录：`water_analysis`

## 1. 项目目标

本目录用于完成 New Jersey 水质硝酸盐（nitrate）热点分析。整体工作从 WQP 原始水质数据开始，经过数据清洗、硝酸盐指标提取、站点统计、热点识别、季节和时间趋势分析、流域关联、土地利用叠加、污水设施/DMR 排放关联、多变量模型、稳健性检验、缓冲区土地利用检验、水文与排口可视化，最终生成网站 dashboard 所需数据、交互地图、图表和研究 proposal。

核心研究问题：

- 哪些监测站点和流域表现出较高硝酸盐水平？
- 硝酸盐热点是否与流域土地利用、设施密度、排放量、水文/降雨等因素相关？
- 这些关系在热点阈值、站点置信度、模型共线性和空间尺度变化下是否稳定？
- 哪些结果可以作为后续研究或 proposal 的依据？

## 2. 当前目录结构

- `app.py`：Flask dashboard 后端，提供页面、API、地图、图表和 proposal 静态资源。
- `main.py`：主流水线入口，按编号脚本顺序执行分析。
- `download_wqp_nj.py`：按月下载并合并 New Jersey WQP 数据。
- `interactive_map.py`：早期硝酸盐交互地图生成脚本。
- `spatial_analysis.py`：空间分析入口。
- `scripts/`：编号分析脚本与外部下载脚本。
- `data/`：原始、合并、处理后和外部辅助数据。
- `output/`：dashboard JSON、地图、图表、表格、proposal、日志和进度报告。
- `templates/`：dashboard、watershed 页面和 proposal 页面模板。

## 3. 数据规模

当前已读取到的主要数据规模如下：

- `data/combined/wqp_nj_2000_2026_combined.csv`
  - 约 5,249,167 行数据。
  - 81 列。
  - 文件大小约 3007.90 MB。
  - 来源为按月下载并合并的 WQP New Jersey 2000-2026 数据。
- `data/resultphyschem.csv`
  - 约 27,507 行。
  - 81 列。
  - 文件大小约 16.59 MB。
  - 为物理化学结果数据。
- `data/station.csv`
  - 约 264 行。
  - 37 列。
  - 文件大小约 61 KB。
  - 为监测站元数据。
- `output/tables/station_summary_for_website.csv`
  - 3,658 个站点汇总记录。
  - 23 列。
- `output/tables/station_detail_index.csv`
  - 3,658 个站点详情索引记录。
  - 11 列。

数据文件数量和体量：

- `data/combined/`：1 个文件，约 3007.90 MB。
- `data/processed/`：41 个文件，约 1479.84 MB。
- `data/external/`：77 个文件，约 1771.38 MB。
- `data/raw_wqp_zips/`：635 个 ZIP 文件，约 307.65 MB。
- `data/raw_wqp_csv_parts/`：634 个 CSV 分片文件，约 3004.28 MB。

## 4. 主流水线

`main.py` 定义了完整执行顺序。当前流水线包含以下步骤：

1. `scripts/01_clean_wqp_data.py`
   - 清洗 WQP 原始数据。
   - 统一关键字段，为后续硝酸盐提取和站点统计准备结构化数据。
   - 输出处理后的数据文件和日志。

2. `scripts/02_extract_nitrate.py`
   - 从清洗后水质结果中提取硝酸盐相关记录。
   - 标准化硝酸盐浓度指标和单位。
   - 为站点级统计、热点识别和时间趋势分析提供输入。

3. `scripts/03_station_summary.py`
   - 按监测站点汇总硝酸盐结果。
   - 计算均值、中位数、最大值、p90、观测次数、置信度、热点标记等。
   - 主要输出：
     - `output/tables/station_summary_for_website.csv`
     - `output/dashboard/summary_cards.json`

4. `scripts/04_export_hotspot_map.py`
   - 生成站点点位和热点点位数据。
   - 生成硝酸盐热点交互地图。
   - 主要输出：
     - `output/dashboard/map_points.json`
     - `output/dashboard/hotspot_points.json`
     - `output/maps/nitrate_hotspot_map.html`

5. `scripts/05_seasonal_analysis.py`
   - 按月份和季节分析硝酸盐变化。
   - 生成季节图表和季节热点对比。
   - 主要输出：
     - `output/dashboard/monthly_chart.json`
     - `output/dashboard/seasonal_chart.json`
     - `output/dashboard/seasonal_hotspot_comparison.json`

6. `scripts/06_moving_average.py`
   - 构建月度移动平均和热点移动平均。
   - 生成年度趋势图表数据。
   - 主要输出：
     - `output/dashboard/monthly_moving_average_chart.json`
     - `output/dashboard/hotspot_moving_average_chart.json`
     - `output/dashboard/yearly_trend_chart.json`

7. `scripts/07_station_detail_export.py`
   - 为每个站点导出单独 JSON 详情文件。
   - 生成站点详情索引。
   - 主要输出：
     - `output/dashboard/station_details/` 下 3,658 个站点 JSON。
     - `output/dashboard/station_detail_index.json`
     - `output/tables/station_detail_index.csv`

8. `scripts/08_watershed_join.py`
   - 将站点与流域边界进行空间关联。
   - 计算流域级硝酸盐均值、热点率、观测数和置信度。
   - 主要输出：
     - `output/dashboard/watershed_summary.json`
     - `output/maps/watershed_hotspot_map.html`

9. `scripts/09_watershed_comparison_map.py`
   - 构建流域对比交互地图。
   - 用于比较不同流域的站点数、热点率和硝酸盐浓度。
   - 主要输出：
     - `output/maps/watershed_comparison_map.html`

10. `scripts/10_land_use_watershed_overlay.py`
    - 叠加流域与土地利用数据。
    - 汇总每个流域的 developed、agriculture、forest、wetlands、barren 等比例。
    - 主要输出：
      - `output/dashboard/watershed_land_use_summary.json`
      - `output/dashboard/watershed_land_use_nitrate_joined.json`

11. `scripts/11_land_use_nitrate_correlation.py`
    - 计算土地利用变量与硝酸盐指标的相关性。
    - 输出相关性表、排名和散点图。
    - 主要输出：
      - `output/dashboard/land_use_nitrate_correlation.json`
      - `output/dashboard/land_use_nitrate_ranking.json`
      - `output/figures/land_use_vs_hotspot_rate_scatter.png`
      - `output/figures/land_use_vs_mean_nitrate_scatter.png`

12. `scripts/12_wastewater_watershed_join.py`
    - 将 NJPDES/污水设施点与流域进行空间关联。
    - 汇总每个流域设施数量、设施密度和设施类型。
    - 主要输出：
      - `output/dashboard/watershed_wastewater_facility_summary.json`
      - `output/dashboard/watershed_land_use_wastewater_nitrate_joined.json`

13. `scripts/13_facility_nitrate_correlation.py`
    - 计算设施密度、设施类型与硝酸盐指标的相关性。
    - 输出设施相关性、排名和散点图。
    - 主要输出：
      - `output/dashboard/facility_nitrate_correlation.json`
      - `output/dashboard/facility_nitrate_ranking.json`
      - `output/figures/facility_density_vs_hotspot_rate_scatter.png`
      - `output/figures/facility_density_vs_mean_nitrate_scatter.png`
      - `output/figures/industrial_stormwater_density_vs_hotspot_rate_scatter.png`
      - `output/figures/septic_groundwater_density_vs_mean_nitrate_scatter.png`

14. `scripts/14_build_discharge_summary.py`
    - 读取本地 DMR discharge summary。
    - 按 normalized permit ID 与 NJPDES facility points 匹配。
    - 汇总设施排放量、匹配率和可用性状态。
    - 主要输出：
      - `output/dashboard/discharge_volume_status.json`
      - `output/dashboard/discharge_permit_match_summary.json`

15. `scripts/15_multivariable_regression.py`
    - 建立多变量回归模型，比较土地利用、设施密度和组合模型。
    - 输出模型 R2、adjusted R2、RMSE、MAE、AIC、BIC、系数、预测和 VIF。
    - 主要输出：
      - `output/dashboard/multivariable_model_comparison.json`
      - `output/dashboard/multivariable_model_coefficients.json`
      - `output/dashboard/multivariable_model_predictions.json`
      - `output/dashboard/multivariable_model_vif.json`
      - `output/figures/multivariable_model_r2_comparison.png`
      - `output/figures/observed_vs_predicted_hotspot_rate.png`
      - `output/figures/observed_vs_predicted_mean_nitrate.png`
      - `output/figures/mean_nitrate_model_coefficients.png`
      - `output/figures/hotspot_rate_model_coefficients.png`
      - `output/figures/mean_nitrate_residuals.png`
      - `output/figures/hotspot_rate_residuals.png`

16. `scripts/16_validate_dashboard_assets.py`
    - 检查 dashboard 引用的图、地图和 proposal 文件是否存在。
    - 日志显示所有被检查资产均存在。
    - 主要输出：
      - `output/logs/16_validate_dashboard_assets_log.txt`

17. `scripts/18_robustness_reliability_model.py`
    - 进行热点阈值稳健性、置信度加权和低 VIF 简化模型检查。
    - 主要输出：
      - `output/dashboard/hotspot_threshold_robustness.json`
      - `output/dashboard/hotspot_threshold_watershed_summary.json`
      - `output/dashboard/confidence_weighted_watershed_summary.json`
      - `output/dashboard/simplified_model_vif_comparison.json`
      - `output/dashboard/rainfall_nitrate_yearly_correlation.json`
      - `output/figures/hotspot_threshold_robustness.png`
      - `output/figures/confidence_weighted_hotspot_comparison.png`
      - `output/figures/simplified_model_r2_vif_comparison.png`
      - `output/figures/rainfall_vs_yearly_nitrate.png`

18. `scripts/19_station_buffer_land_use.py`
    - 在站点周边不同半径缓冲区内计算土地利用比例。
    - 比较局部尺度土地利用与站点硝酸盐指标的相关性。
    - 主要输出：
      - `output/dashboard/station_buffer_land_use_summary.json`
      - `output/dashboard/station_buffer_land_use_correlation.json`
      - `output/figures/buffer_land_use_scale_correlation.png`
      - `output/figures/buffer_developed_vs_nitrate_by_scale.png`

19. `scripts/20_additional_factors_hydrology_discharge.py`
    - 纳入降雨、DMR 排放、水文/上游代理变量等附加因素。
    - 计算附加变量与硝酸盐指标的相关性，并比较扩展模型。
    - 主要输出：
      - `output/dashboard/additional_factor_nitrate_correlation.json`
      - `output/dashboard/additional_factor_model_comparison.json`
      - `output/dashboard/watershed_additional_factors_joined.json`
      - `output/figures/additional_factors_correlation.png`
      - `output/figures/watershed_rainfall_vs_mean_nitrate.png`
      - `output/figures/hydrology_proxy_vs_hotspot_rate.png`

20. `scripts/21_hydrography_outfall_visualization.py`
    - 读取 NHDPlus flowline，并将 DMR/NJPDES 设施点生成 snapped outfall proxy。
    - 建立水文-排口上下文地图。
    - 主要输出：
      - `output/dashboard/hydrography_outfall_status.json`
      - `output/dashboard/dmr_outfall_snapped_proxy_points.json`
      - `output/dashboard/dmr_permit_feature_summary.json`
      - `output/dashboard/watershed_outfall_feature_summary.json`
      - `output/dashboard/watershed_hydrography_flowline_summary.json`
      - `output/maps/hydrography_outfall_context_map.html`

21. `scripts/17_export_research_proposal.py`
    - 汇总所有核心指标和图表。
    - 导出研究 proposal 的 Markdown 和 HTML 文件。
    - 主要输出：
      - `output/proposal/nj_nitrate_research_proposal.md`
      - `output/proposal/nj_nitrate_research_proposal.html`
      - `output/dashboard/research_proposal_summary.json`

附加下载脚本：

- `scripts/download_nhdplus_hu4.py`：下载 NHDPlus HU4 数据。
- `scripts/download_nhd_flowlines_arcgis.py`：从 ArcGIS 服务下载 NHD flowlines。

## 5. 核心站点结果

来自 `output/dashboard/summary_cards.json`：

- 总站点数：3,658。
- 热点站点数：411。
- 高置信度站点：76。
- 中置信度站点：253。
- 低置信度站点：3,329。
- 全部站点平均硝酸盐：0.7075 mg/L。
- 全部站点中位数硝酸盐：0.2895 mg/L。
- 全部站点最大硝酸盐：156.0 mg/L。
- p90 最高站点：`NJDEP_BFBM-NJW04459-352-3`。
- 热点定义：基于站点级 mean 或 p90 nitrate 进入前 10%。
- 注意：低置信度热点需要谨慎解释。

## 6. 流域热点结果

来自 `output/dashboard/watershed_summary.json`，共有 21 个流域汇总。热点率最高的流域包括：

| 排名 | 流域 | 站点数 | 热点站点数 | 热点率 | 平均硝酸盐 mg/L |
|---:|---|---:|---:|---:|---:|
| 1 | Lower Passaic and Saddle | 87 | 50 | 57.47% | 2.199 |
| 2 | Hackensack, Hudson, and Pascack | 107 | 36 | 33.64% | 1.915 |
| 3 | Maurice, Salem, and Cohansey | 327 | 103 | 31.50% | 1.391 |
| 4 | Millstone | 151 | 31 | 20.53% | 1.067 |
| 5 | Lower Delaware | 150 | 29 | 19.33% | 1.108 |
| 6 | North and South Branch Raritan | 229 | 40 | 17.47% | 1.066 |
| 7 | Upper Passaic, Whippany, and Rockaway | 209 | 33 | 15.79% | 0.862 |
| 8 | Lower Raritan, South River, and Lawrence | 134 | 18 | 13.43% | 1.068 |

## 7. 土地利用相关性结果

来自 `output/dashboard/land_use_nitrate_correlation.json`：

最重要结果是 developed land 与硝酸盐指标稳定正相关。

主要相关性：

- `developed_percent` vs `mean_nitrate_mg_L`
  - Pearson r = 0.6827。
  - Spearman r = 0.6455。
- `developed_percent` vs `mean_p90_nitrate_mg_L`
  - Pearson r = 0.6306。
  - Spearman r = 0.5714。
- `developed_percent` vs `hotspot_rate_percent`
  - Pearson r = 0.5680。
  - Spearman r = 0.5677。
- `barren_percent` vs `mean_p90_nitrate_mg_L`
  - Pearson r = 0.5566。
  - Spearman r = 0.4468。
- `forest_percent` vs `mean_p90_nitrate_mg_L`
  - Pearson r = -0.4351。
  - Spearman r = -0.3610。

解释：

- 建成用地比例越高，流域级平均硝酸盐、p90 硝酸盐和热点率通常越高。
- 森林比例与硝酸盐指标整体呈负相关。
- 这些是流域尺度统计关联，不是因果证明。

## 8. 污水设施/排放相关结果

来自 `output/dashboard/facility_nitrate_correlation.json`：

主要设施相关性：

- `industrial_stormwater_facility_count` vs `mean_nitrate_mg_L`
  - Pearson r = 0.6797。
  - Spearman r = 0.5742。
- `facility_density_per_100_km2` vs `mean_nitrate_mg_L`
  - Pearson r = 0.6631。
  - Spearman r = 0.6130。
- `industrial_stormwater_density_per_100_km2` vs `mean_p90_nitrate_mg_L`
  - Pearson r = 0.6618。
  - Spearman r = 0.4571。
- `industrial_stormwater_density_per_100_km2` vs `mean_nitrate_mg_L`
  - Pearson r = 0.6617。
  - Spearman r = 0.5286。
- `facility_count` vs `mean_nitrate_mg_L`
  - Pearson r = 0.6169。
  - Spearman r = 0.5530。

DMR discharge 匹配状态来自 `output/dashboard/discharge_volume_status.json`：

- DMR 数据状态：loaded。
- DMR permit 数：709。
- facility permit 数：3,571。
- 总 facility 数：3,574。
- 匹配到 DMR 的唯一 permit：41。
- 匹配到 DMR 的 facilities：32。
- facility 匹配率：0.8954%。
- permit 匹配率：1.1481%。
- 匹配流域数：13。
- general permit facilities：2,994。
- individual NPDES-like facilities：580。
- 当前 outfall location 和 flowline network 在 Step 14 本地输入中不可用。

解释：

- 设施密度与硝酸盐有中等强度正相关。
- DMR 流量数据可用，但与 NJPDES facility points 的 ID 精确匹配率较低。
- 由于大量设施使用 general permit IDs，DMR 表与 facility 表无法一对一直接匹配。

## 9. 多变量模型结果

来自 `output/dashboard/multivariable_model_comparison.json`：

按 adjusted R2 选出的主要模型：

| 目标变量 | 最佳模型 | predictors | R2 | adjusted R2 |
|---|---|---|---:|---:|
| `hotspot_rate_percent` | `land_use_only` | `developed_percent, agriculture_percent` | 0.3417 | 0.2685 |
| `mean_nitrate_mg_L` | `combined_extended` | 土地利用 + facility density + facility type density | 0.6466 | 0.4564 |
| `mean_p90_nitrate_mg_L` | `combined_extended` | 土地利用 + facility density + facility type density | 0.6704 | 0.4929 |
| `max_station_nitrate_mg_L` | `combined_extended` | 土地利用 + facility density + facility type density | 0.6110 | 0.4015 |

VIF 结果来自 `output/dashboard/multivariable_model_vif.json`：

- `developed_percent` VIF = 10.9544，高共线性。
- `agriculture_percent` VIF = 2.2432，可接受。
- `facility_density_per_100_km2` VIF = 3198.3036，高共线性。

解释：

- 扩展模型在 mean、p90、max 指标上表现较好。
- 但部分 facility density 变量存在极高共线性，因此不能只看 R2。
- 对 hotspot rate 而言，土地利用模型更稳健。

## 10. 稳健性与置信度检查

来自 `output/dashboard/hotspot_threshold_robustness.json`：

| 阈值 | mean cutoff mg/L | p90 cutoff mg/L | 热点站点数 | 热点站点比例 | Top 5 流域与 10% 阈值 Jaccard |
|---|---:|---:|---:|---:|---:|
| top 5% | 2.5100 | 3.1178 | 208 | 5.71% | N/A |
| top 10% | 1.7036 | 2.1448 | 410 | 11.25% | 1.0000 |
| top 20% | 1.0810 | 1.3495 | 807 | 22.15% | 0.6667 |

来自 `output/dashboard/simplified_model_vif_comparison.json` 的低 VIF 模型：

| 目标变量 | 最佳低 VIF 模型 | predictors | R2 | adjusted R2 | max VIF |
|---|---|---|---:|---:|---:|
| `hotspot_rate_percent` | `developed_only` | `developed_percent` | 0.3226 | 0.2870 | 1.0 |
| `mean_nitrate_mg_L` | `developed_agriculture` | `developed_percent, agriculture_percent` | 0.5045 | 0.4495 | 1.0664 |
| `mean_p90_nitrate_mg_L` | `industrial_only` | `industrial_stormwater_density_per_100_km2` | 0.4380 | 0.4084 | 1.0 |

来自 `output/dashboard/rainfall_nitrate_yearly_correlation.json`：

- 年降雨量 vs 年均硝酸盐：
  - Pearson r = 0.1721。
  - Spearman r = 0.1556。
- 解释：按年度聚合看，降雨与平均硝酸盐关系较弱。

## 11. 站点缓冲区土地利用结果

来自 `output/dashboard/station_buffer_land_use_correlation.json`：

- 已对 3,658 个站点计算不同半径缓冲区的土地利用。
- 500 m 缓冲区示例结果：
  - `developed_percent` vs `mean_nitrate_mg_L`：Pearson r = 0.1568，Spearman r = 0.4316。
  - `developed_percent` vs `p90_nitrate_mg_L`：Pearson r = 0.0983，Spearman r = 0.4300。
  - `agriculture_percent` vs `mean_nitrate_mg_L`：Pearson r = 0.1630，Spearman r = 0.3139。
- proposal 摘要中记录的最佳缓冲区结果：
  - 最佳半径：5000 m。
  - 最佳变量：`agriculture_percent`。
  - 最佳 Pearson r = 0.2086。

解释：

- 局地缓冲区结果比流域尺度结果弱。
- developed land 在流域尺度上更稳定，局地缓冲区土地利用需要结合采样位置、流向和水文连通性进一步解释。

## 12. 附加因素、水文和排口结果

来自 `output/dashboard/additional_factor_nitrate_correlation.json`：

较强的附加因素相关性包括：

- `mean_facility_nitrogen_load` vs `hotspot_rate_percent`
  - Pearson r = -0.8442。
  - Spearman r = -0.9000。
- `mean_facility_nitrogen_load` vs `mean_nitrate_mg_L`
  - Pearson r = -0.7658。
  - Spearman r = -0.8000。
- `upgradient_facility_density_proxy_per_100_km2` vs `mean_p90_nitrate_mg_L`
  - Pearson r = 0.6304。
  - Spearman r = 0.6714。
- `upgradient_facility_density_proxy_per_100_km2` vs `mean_nitrate_mg_L`
  - Pearson r = 0.5615。
  - Spearman r = 0.6143。
- `p90_annual_precip_inches` vs `hotspot_rate_percent`
  - Pearson r = 0.5613。
  - Spearman r = 0.5339。

来自 `output/dashboard/additional_factor_model_comparison.json`：

| 目标变量 | 最佳扩展模型 | predictors | R2 | adjusted R2 | max VIF |
|---|---|---|---:|---:|---:|
| `hotspot_rate_percent` | `developed_agriculture_discharge` | developed, agriculture, total facility discharge | 0.4689 | 0.3693 | 1.2093 |
| `mean_nitrate_mg_L` | `developed_agriculture_discharge` | developed, agriculture, total facility discharge | 0.5809 | 0.5023 | 1.2093 |

来自 `output/dashboard/hydrography_outfall_status.json`：

- 状态：loaded。
- DMR ZIP 文件夹：`data/external/discharge/npdes_dmr_limits_by_fy`。
- NHDPlus 来源：`NHDPLUS_H_0206_HU4_GDB.zip`。
- permit feature count：1,295。
- matched to facility watershed：79。
- snapped outfall proxy count：47。
- median snap distance：518.94 m。
- flowline segment count：12,925。
- outfall coordinate status：`snapped_proxy_generated`。
- flowline network status：`loaded_intersecting_flowlines`。
- 地图：`output/maps/hydrography_outfall_context_map.html`。

来自 `output/dashboard/watershed_hydrography_flowline_summary.json`：

- 20 个流域具有 flowline summary。
- flowline 总段数在各流域汇总后用于水文背景展示。

来自 `output/dashboard/watershed_outfall_feature_summary.json`：

- 14 个流域具有 DMR permit feature summary。
- 包括 DMR permit feature count、EXO feature count、flow feature record count、nitrogen feature record count。

解释：

- Step 21 已经把可用的 facility/DMR 点位投影到 NHD flowlines 上，形成 proxy outfall。
- 这些不是原始真实 outfall 坐标，而是用 NJPDES facility point snapped 到最近 NHD flowline 的代理点。
- 全 NJ 覆盖仍需要补充更多 HU4 NHDPlus HR FileGDB ZIP 后重新运行 Step 21。

## 13. 研究 proposal 摘要结论

来自 `output/dashboard/research_proposal_summary.json`：

主结论：

> Developed land remains the most stable watershed-level predictor after threshold, confidence, weighting, rainfall, buffer-scale, DMR discharge, hydrology/upstream proxy, and low-VIF model checks. Facility density and matched DMR flow are useful exploratory factors, but they do not yet prove independent causal effects after developed land is included.

中文解释：

- 建成用地比例是目前最稳定的流域尺度硝酸盐预测因子。
- 这个结论在热点阈值、站点置信度、加权、降雨、缓冲区尺度、DMR discharge、水文/上游 proxy、低 VIF 模型等检查后仍然相对稳定。
- facility density 和 matched DMR flow 有探索价值。
- 但在加入 developed land 后，它们还不能单独证明独立因果效应。

proposal 中记录的关键指标：

- hotspot land-use adjusted R2：0.2685。
- hotspot facility adjusted R2：0.2575。
- mean land-use adjusted R2：0.4495。
- mean facility adjusted R2：0.4155。
- p90 land-use adjusted R2：0.3388。
- p90 extended adjusted R2：0.4929。
- top 20% 与 top 10% 热点阈值下 Top 5 流域 Jaccard：0.6667。
- rainfall Pearson r：0.1721。
- rainfall Spearman r：0.1556。
- discharge matched facilities：32。
- discharge matched watersheds：13。
- discharge total facilities：3,574。
- snapped outfall proxy count：47。
- median snap distance：518.94 m。
- flowline segment count：12,925。
- discharge hotspot adjusted R2：0.3693。
- discharge mean adjusted R2：0.5023。
- hotspot developed-only R2：0.3226。
- hotspot developed + agriculture R2：0.3417。
- mean developed + agriculture adjusted R2：0.4495。

## 14. Dashboard 和网站接口

`app.py` 提供三个页面：

- `/`：主 dashboard。
- `/watersheds`：流域分析页面。
- `/proposal`：proposal 页面。

主要 API：

- `/api/summary`
- `/api/seasonal-chart`
- `/api/monthly-chart`
- `/api/yearly-trend`
- `/api/monthly-moving-average`
- `/api/hotspot-moving-average`
- `/api/station-index`
- `/api/station-detail/<filename>`
- `/api/watershed-summary`
- `/api/watershed-land-use`
- `/api/land-use-correlation`
- `/api/land-use-ranking`
- `/api/facility-nitrate-correlation`
- `/api/facility-nitrate-ranking`
- `/api/multivariable-model-comparison`
- `/api/multivariable-model-coefficients`
- `/api/multivariable-model-predictions`
- `/api/multivariable-model-vif`
- `/api/research-proposal-summary`
- `/api/hotspot-threshold-robustness`
- `/api/confidence-weighted-watershed`
- `/api/simplified-model-vif-comparison`
- `/api/rainfall-nitrate-correlation`
- `/api/station-buffer-land-use-correlation`
- `/api/additional-factor-correlation`
- `/api/additional-factor-model-comparison`
- `/api/discharge-volume-status`
- `/api/discharge-permit-match-summary`
- `/api/hydrography-outfall-status`
- `/api/watershed-outfall-feature-summary`
- `/api/watershed-hydrography-flowline-summary`
- `/api/dmr-outfall-snapped-proxies`

静态资产路由：

- `/maps/<filename>`
- `/figures/<filename>`
- `/proposal-output/<filename>`

## 15. 当前输出资产

Dashboard JSON：

- `output/dashboard/` 当前共有 3,699 个文件，约 57.69 MB。
- 其中 `output/dashboard/station_details/` 有 3,658 个站点详情 JSON。

图表：

- `output/figures/` 当前共有 22 个 PNG，约 2.50 MB。
- 主要图表包括：
  - `additional_factors_correlation.png`
  - `buffer_developed_vs_nitrate_by_scale.png`
  - `buffer_land_use_scale_correlation.png`
  - `confidence_weighted_hotspot_comparison.png`
  - `facility_density_vs_hotspot_rate_scatter.png`
  - `facility_density_vs_mean_nitrate_scatter.png`
  - `hotspot_threshold_robustness.png`
  - `hydrology_proxy_vs_hotspot_rate.png`
  - `land_use_vs_hotspot_rate_scatter.png`
  - `land_use_vs_mean_nitrate_scatter.png`
  - `multivariable_model_r2_comparison.png`
  - `observed_vs_predicted_hotspot_rate.png`
  - `observed_vs_predicted_mean_nitrate.png`
  - `rainfall_vs_yearly_nitrate.png`
  - `simplified_model_r2_vif_comparison.png`
  - `watershed_rainfall_vs_mean_nitrate.png`

地图：

- `output/maps/hydrography_outfall_context_map.html`，约 9.50 MB。
- `output/maps/nitrate_hotspot_map.html`，约 8.34 MB。
- `output/maps/watershed_comparison_map.html`，约 13.57 MB。
- `output/maps/watershed_hotspot_map.html`，约 8.51 MB。

Proposal：

- `output/proposal/nj_nitrate_research_proposal.md`，约 22 KB。
- `output/proposal/nj_nitrate_research_proposal.html`，约 25 KB。

进度报告：

- `output/progress_report_2026-06-09/Water_Analysis_Progress_Proposal_2026-06-09.docx`
- `output/progress_report_2026-06-09/dashboard.png`
- `output/progress_report_2026-06-09/watersheds.png`
- `output/progress_report_2026-06-09/proposal_page.png`
- `output/progress_report_2026-06-09/generate_progress_report.ps1`

日志：

- `output/logs/` 当前共有 23 个日志文件。
- `16_validate_dashboard_assets_log.txt` 显示 dashboard 引用的图、地图和 proposal 文件均存在。

## 16. 当前限制和注意事项

- 当前分析主要是统计关联，不能直接作为因果结论。
- 站点数据置信度差异明显：3,329 个站点为低置信度，热点解释应优先关注高/中置信度站点。
- DMR discharge 与 NJPDES facility points 的 permit ID 精确匹配率较低，facility-level discharge 结论需要谨慎。
- Step 21 的 outfall 点是 snapped proxy，不是真实 outfall 坐标。
- NHDPlus 当前只明确读取到 `NHDPLUS_H_0206_HU4_GDB.zip`，若需要完整 NJ 水文覆盖，应补齐相关 HU4 数据后重跑。
- 多变量模型中部分 facility density 变量 VIF 极高，说明它们与其他变量高度共线。
- 土地利用、设施和水文变量均为流域或代理尺度变量，不能替代现场机制验证。

## 17. 最终结论

当前 `water_analysis` 已形成完整的 New Jersey 硝酸盐热点分析工作流。主要交付物包括：

- 清洗和处理后的 WQP 数据。
- 3,658 个站点级硝酸盐统计和详情。
- 21 个流域级硝酸盐热点统计。
- 土地利用、设施密度、DMR discharge、水文/排口和降雨相关分析。
- 多变量模型、VIF、稳健性和置信度检查。
- 4 个交互式 HTML 地图。
- 22 张图表。
- Dashboard API 和页面模板。
- 研究 proposal Markdown/HTML。

最稳健的研究结论是：建成用地比例是目前最稳定的流域尺度硝酸盐预测因子。设施密度和 DMR discharge 有进一步研究价值，但目前更多是探索性证据，不能单独证明独立因果效应。
