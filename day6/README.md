# Snapshot dùng lại từ Lab6

Nguồn: [Lab6 tại commit `e0865fa`](https://github.com/Youngboy1609/K5-L3-Day06-DataIngestionEngineering/tree/e0865fa4b242bffb116216c0dd7a225d32bbb0d1). Các file được sao nguyên byte và liệt kê kèm SHA-256 trong [provenance](../data/day6_provenance.json).

- `data/`: PDF được phép chia sẻ, manifest và attribution.
- `starter/src/`: ingestion, chunking, embedding CUDA, pgvector và runner Lab6 để tái tạo index.
- `starter/artifacts/strategies.json`: cấu hình embedding/index gốc; `starter/requirements.txt` dành cho Python 3.11 và CUDA.
- `starter/docker-compose.yml`, `init.sql`, `.env.example`, `scripts/check_setup.py`: hạ tầng tái tạo local.
- `starter/tests/`: test logic kế thừa của Lab6.
- `benchmark/`: benchmark/protocol **lịch sử** của Lab6; chưa phải benchmark Lab7.

Lab7 sẽ nối dense retriever vào index Lab6. Chưa chạy import vào database, chưa thay bảng/index cũ, chưa kết nối model agent thật. Không chạy `ingest` vào database Lab6 đang giữ bằng chứng khi chỉ cần đọc index; nếu tái tạo, dùng database/volume riêng và ghi rõ kết nối. Runner Lab6 ghi output vào `day6/starter/results/`, không phải kết quả Lab7.

Không mang `.env` thật, venv, cache embedding, model weights, Docker volume hay log tạm từ Lab6 sang. Xem [handoff](../docs/DAY6_REUSE.md) để tiếp tục.
