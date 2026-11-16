# Context Lab6 và yêu cầu chuyển tiếp Lab7

> Đây là bản ghi context lúc khởi tạo. Kiến thức/snapshot Lab6 được giữ để truy vết; trạng thái triển khai và kết quả cuối ở `RUN_LAB7.md` và báo cáo cá nhân. Các mục “chưa triển khai/chưa có kết quả” phía dưới mô tả thời điểm khởi tạo, không phải trạng thái hiện tại.

## Nguồn đã đọc

Đã đọc toàn bộ tài liệu, starter, fixtures và tests trong repo đề Lab7 tại commit `c67ec62`: README, GUIDE, BENCHMARK, RULES, RUBRIC, SUBMISSION, ADVANCED, AGENT_SETUP, PSEUDOCODE, CHECKPOINTS và các mẫu báo cáo. Bản đề và lịch sử Git được giữ trong checkout này; `origin` là repo cá nhân và `upstream` là repo đề.

Lab6 được giữ riêng tại `D:\K5-L3-Day06-DataIngestionEngineering`, commit `e0865fa4b242bffb116216c0dd7a225d32bbb0d1`. Snapshot cần để tái tạo nằm ở `day6/`, hash từng file ở `data/day6_provenance.json`. Không sao chép kết quả Lab6 thành kết quả Lab7.

## Kiến thức và bằng chứng Lab6

- Corpus: *Think Python, 2nd edition*, v2.4.1, CC BY-NC 3.0; whitelist 35 trang vật lý (93–100, 111–121, 125–133, 137–143), 59.899 ký tự. Trang in bằng trang vật lý trừ 22.
- Extraction giữ layout, đoạn và thụt lề code. A là cửa sổ 500 ký tự, 138 chunk; B/C là block/đoạn giới hạn 500 ký tự, 159 chunk. B/C giữ nguyên ID, text và vector, chỉ C áp dụng chapter filter do query cung cấp.
- Embedding Qwen3-Embedding-0.6B local CUDA FP16, 1024 chiều, normalize, document không có query prompt, query dùng prompt `query`; revision đã ghim trong provenance. Không được đổi model/dimension rồi dùng lại vector cũ.
- PostgreSQL 16.16 / pgvector 0.8.7, exact cosine; bảng `lab_chunks` có khóa `(strategy, chunk_id)`. Index lịch sử 456 hàng; C/B mỗi strategy 159 hàng. Chọn một strategy cố định khi xuất chunk để tránh trùng B/C.
- Metadata nguồn cũ `data/thinkpython2.pdf` là đường dẫn logic theo root Lab6; trong bài Lab7, file gốc tương ứng là `day6/data/thinkpython2.pdf`. Adapter/citation cần ánh xạ đường dẫn này mà giữ nguyên document ID, page và chunk ID để truy vết.
- Lab6 dev: A/B/C đều Hit@1 10/16 và Evidence Hit@3 12/16. Test-v2: A 6/8 và 7/8; B/C 6/8 và 6/8. Đây là số liệu lịch sử, không đánh giá agent Lab7.
- `dict-07`: strict metric bỏ sót evidence ở trang kề 128/129; cần khai báo evidence thay thế trước khi đánh giá mới. `tuple-08` là lỗi retrieval về hashability/immutable keys. Bốn gold (`str-01`, `dict-04`, `list-08`, `dict-08`) từng được Gemini gắn cờ hỗ trợ một phần/context ngắn; cần rà đầy đủ nguồn khi chuẩn bị nhãn mới.
- Nhãn chất lượng Lab6 là Gemini/AGY hỗ trợ và được tác giả chấp thuận, không phải annotation độc lập. Không dùng nhãn này để tự động suy ra grounded answer/citation correctness của Lab7.
- CUDA smoke, snapshot và 11 tests Lab6 đã đạt ngày 2026-11-14. Từng OOM khi nhiều ứng dụng mở và đạt sau khi đóng VS Code; môi trường có system-site-packages và chưa clean replay. Đây là bằng chứng lịch sử, chưa revalidate hôm nay.
- Giữ nguyên byte khi fingerprint: `.gitattributes` trong repo mới bảo vệ snapshot Lab6 khỏi đổi CRLF/LF. Không mang `.env`, cache/weights/venv, local plan hoặc output tạm vào Git.

## Khoảng cách phải hoàn thành cho Lab7

1. Agent dùng model thật điều phối retrieval, có tool trace, điều kiện dừng, context budget, citation và abstention. Model/provider chưa chọn; chưa gọi API.
2. Ít nhất ba **phương pháp** retrieval, gồm dense trên store Lab6. A/B/C Lab6 là cấu hình dữ liệu/filter, không tự được tính là ba phương pháp Lab7. Dense + lexical + hybrid là một hướng đơn giản để xem xét, chưa triển khai hoặc đo.
3. Benchmark mới tối thiểu 24 câu: dev >=15 có đáp án +2 thiếu evidence; test >=5 có đáp án +2 thiếu evidence. Toàn bộ câu Lab6 đã được xem; chỉ tái dùng làm dev/exploratory, không gắn lại nhãn test độc lập.
4. Ít nhất hai cấu hình cải thiện trên dev, hai lỗi dev được phân tích, tiêu chí chọn chốt trước test; baseline và cấu hình chọn phải chạy agent thật trên cùng test.
5. Báo Hit@1, Evidence Hit@3, Context Evidence Rate, nhãn context và grounded answer 0/1/2, citation hỗ trợ nội dung, abstention, tool use, latency/chi phí và lỗi. Khớp ID/quote không thay xác minh semantic support.
6. Bonus riêng: một tài liệu thực tế >=100 trang, index nội dung hữu ích gồm text/bảng/ảnh/biểu đồ; dev >=18 và test >=30 câu theo phân nhóm ADVANCED. Chỉ đủ điều kiện +15 khi hoàn tất và test >=90% (ví dụ 27/30); corpus 35 trang hiện tại chưa đáp ứng. Phần cơ bản tối đa 85 điểm.

## Phạm vi thư mục bài nộp hiện tại

Đây là bước chuẩn bị: giữ starter/tests gốc của đề, snapshot Lab6 có provenance, thư mục benchmark/results có hướng dẫn và mẫu báo cáo cá nhân đã điền danh tính/context. Chưa có kết quả Lab7; các bảng báo cáo còn trống có chủ ý. Chưa commit hay push thay đổi chuẩn bị.
