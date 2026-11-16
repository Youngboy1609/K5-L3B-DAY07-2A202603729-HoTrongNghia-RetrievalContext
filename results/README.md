# Kết quả Lab7

Kết quả hiện hành: core test D0-ready8/8; bonus H2-v4-A 26/30, chưa đủ 27/30 để nhận15 điểm. V3 H2-release23/30 được lưu làm lịch sử; không so trực tiếp các bộ test khác nhau. Trace JSONL chứa query, tool calls/arguments/rankings, context, answer/citation, lỗi, latency và cost; file summary và reviews-final/metrics-final đi kèm ghi rõ mẫu số và cách chấm.

Core chọn D0 trên dev nên baseline/selected dùng chung một test run. Điểm bắt đầu đọc: core/dev/comparison-final.json, core/selection-final.json, core/reviews-final.json, bonus/dev/reviews-final.json và bonus/test/reviews-final.json (v4). Freeze root/suite riêng giữ hash nguồn/config/benchmark/DB; historical manifests chỉ là record lịch sử, không đại diện code hiện tại.

Test core D0/H2 thuộc bộ v1, D0-final thuộc v2 và D0-ready thuộc release hiện tại; các benchmark-v*-historical đi kèm. Bonus H2-v2-final và semantic_grades20/30 là lịch sử; H2-release23/30/reviews-v3-historical là kết quả v3 lịch sử; v4 là kết quả hiện hành. Không trộn các run thành điểm cuối hoặc coi hai bộ test khác nhau là paired comparison. Review bonus reviews.json là review gold v2 lịch sử.

Các lượt dev trước context/citation fixes chỉ dùng để giải thích lỗi, không gộp như ablation cùng code cuối. Dev H2-release-complete gồm8+16 câu, component được công khai do process gián đoạn. Raw-query-retrieval báo riêng truy vấn gốc, không gọi LLM. Artifact thử dư và nhãn core keyword đã rút giữ local; không thuộc bài nộp. Xem [audit](../docs/SUBMISSION_AUDIT.md) và [báo cáo](../report/individual/2A202603729_HoTrongNghia.md).
