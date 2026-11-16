# Đối chiếu bài nộp Lab7

Phạm vi: code, dữ liệu được phép chia sẻ hoặc cách tái tạo, benchmark, kết quả và báo cáo. Giữ nguyên tài liệu đề và template gốc. Chưa phát hành lên remote trong lượt hoàn thiện này.

| Yêu cầu | Bằng chứng hiện hành |
|---|---|
| Agent thật, ít nhất ba phương pháp | src/agent.py; src/retrieval.py; src/bonus_retrieval.py; configs/D0,L0,H1,H2.json |
| Core kế thừa Lab6, local CUDA | data/core/export_manifest.json; data/day6_provenance.json; day6/; docs/RUN_LAB7.md |
| Corpus và benchmark, dev/test tách riêng | benchmark/core/questions.jsonl; benchmark/bonus/questions.jsonl; benchmark/protocol.json |
| Hai cấu hình cải thiện và chọn bằng dev | results/core/dev/comparison-final.json; results/core/selection-final.json; báo cáo phân tích các biến thể không vượt D0 |
| Query gốc và query viết lại | results/core/dev/raw-query-retrieval.json; results/bonus/dev/raw-query-retrieval.json; queries/filter thực trong từng trace |
| Context, answer, citation, abstention, tool, latency/cost | results/core/reviews-final.json; results/core/metrics-final.json; results/core/test/D0-ready.jsonl và summary |
| Hai lỗi dev, trước/sau | Báo cáo; results/bonus/dev/H2-after-vision-fix.jsonl; H2-context-v3.jsonl và targeted-review; H2-release-complete.jsonl và reviews-final |
| Freeze source/config/DB trước test | results/run_manifest.json; results/core/run_manifest.json; src/freeze.py; tests/test_freeze_guard.py |
| Bonus nguồn276 trang, index/coverage/region | data/bonus/manifest.json; data/bonus/index/; guide rebuild PDF local, không phát hành ảnh |
| Bonus toàn bộ30 test và nhóm | results/bonus/test/H2-v4-A.jsonl; reviews-final.json; results/bonus/metrics-final.json:26/30, chưa đạt27/30; hai lỗi hệ thống được tính trong mẫu số |
| Lịch sử và giới hạn | results/history/; historical benchmarks; bonus H2-v2-final/semantic_grades; không dùng nhãn core keyword đã rút |
| Báo cáo cá nhân | report/individual/2A202603729_HoTrongNghia.md |

Baseline core chính là D0 được chọn, dùng chung một test run. Kết quả8/8 không tự quy đổi thành điểm85/85; giảng viên chấm theo rubric. Nhãn là AI-assisted có đối chiếu nguồn, không thay xác nhận người học đã tự đọc bài.

Kết quả bonus release23/30 và v2 lịch sử20/30 dùng bộ test khác nhau; không tuyên bố mức tăng có kiểm soát. Chart-04 dev đã có citation sau bounded repair. Một citation phân trang bonus release được chấm fail chặt; chấp nhận nó cũng chỉ24/30.

Các kết quả trung gian không dùng cho kết luận được chuyển vào .lab-local/archive/ và bị Git bỏ qua. Lịch sử test chính thức và evidence phân tích lỗi được giữ có chủ đích. .env, plans, weights, venv, crops, scratch và logs không thuộc bộ nộp. Tổng ledger cuối $0.9687035301/$1.50, reserved0.

Người học còn phải đọc/hiểu báo cáo và các nhãn, kiểm tra quyền truy cập repo, rồi nộp link theo hướng dẫn lớp. Không ghi thay xác nhận thủ công này.

Kiểm tra cuối16/11/2026: unittest discover61/61; pip check không lỗi; validate-benchmark xác nhận core26/bonus54 với đủ nhóm; freeze guard xác nhận cả hai live DB và inputs. Validator cấu trúc vẫn yêu cầu semantic overlap review, được đáp ứng bằng record source/overlap review có công khai giới hạn, không coi validator là semantic judge. Kiểm tra whitespace dùng cr-at-eol vì bảo toàn byte CRLF; src/model.py có một dòng trắng cuối file, giữ nguyên để không đổi fingerprint thí nghiệm.

starter/baseline.py chỉ ghi nhận CRLF đúng byte đã dùng trong thí nghiệm, không đổi nội dung/logic; git diff --ignore-space-at-eol không có thay đổi. Đã kiểm tra SHA256 của41 frozen files được chia sẻ trực tiếp trên Git blobs, tránh trường hợp checkout Windows khớp hash nhưng bản clone mới không khớp. Hai raw bonus JSONL còn lại được tái tạo local theo guide, không đưa vào Git.
