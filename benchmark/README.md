# Benchmark Lab7

Benchmark đang dùng: core26 câu (18 dev,8 test release), bonus54 câu (24 dev,30 test release). Mỗi câu có ID, split, answer/evidence hoặc absence_reason. Filter chỉ lấy từ query; gold không truyền vào agent/tool. Xem [protocol](protocol.json), [source review bonus](../results/bonus/benchmark-release-review.json) và [báo cáo](../report/individual/2A202603729_HoTrongNghia.md).

Các câu `day6/benchmark/questions.jsonl` đã được xem trong Lab6; chỉ là nguồn dev/exploratory. Không chuyển `historical_test` hoặc `test` cũ thành test mới của Lab7. Chốt test/tiêu chí chọn trước thử nghiệm; không gửi gold/expected_answer vào agent/tool.

Các file questions-v*-historical.jsonl là bộ đã lộ trước đây, giữ để truy vết. Kết quả cuối nằm ở results/core/test/D0-ready.jsonl (8/8) và results/bonus/test/H2-release.jsonl (23/30, chưa đạt bonus). Hai lần bonus dùng bộ test khác nhau, không phải phép so sánh cải thiện có kiểm soát. Review ba subagent trong results/bonus/reviews.json thuộc v2 lịch sử; review release mới nằm riêng, có công khai các trang/hình trùng và giới hạn wording chart-03.
