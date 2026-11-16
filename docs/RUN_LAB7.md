# Chạy và tái lập Lab7

Dùng Windows/Python3.11 và Python trong .venv. Cài môi trường:

    python -m venv .venv
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    .venv\Scripts\python.exe -m pip check
    Copy-Item .env.example .env

Điền key trong .env; không commit hoặc in key. Trần API_BUDGET_USD tính trên tổng ledger hiện có, không xóa/reset ledger để có thêm ngân sách. Lượt cuối ghim GLM-5.3-Flash/Wafer, fallback tắt. Relace rẻ hơn nhưng các lượt thật gặp HTTP500/unknown usage; xem results/runtime/provider-selection.json.

Embedding: Qwen/Qwen3-Embedding-0.6B revision97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3, CUDA FP16,1024 chiều, normalized,max512 tokens. Documents không có query instruction; query dùng prompt query. Runtime dùng local_files_only=True: tải weights vào Hugging Face cache trước; cache được tái sử dụng, không gọi đó là cold download. Không nộp weights/venv.

Tải snapshot đã ghim một lần (cần mạng, không gọi inference API):

    .venv\Scripts\python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen3-Embedding-0.6B', revision='97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3')"

## Dữ liệu và database

Core:159 chunks/vectors C từ Day6 ở data/core/chunks.json. PDF/attribution Think Python ở day6/data/, CC BY-NC3.0, dùng cho coursework. Bonus: tải đúng URL/hash trong data/bonus/manifest.json vào .lab-local/research/wdr2024-full-candidate.pdf; không nộp PDF/crop bonus. Người chấm có nguồn truy cập qua UN Digital Library/DOI.

Docker Desktop phải chạy:

    docker compose up -d --wait
    docker compose --profile replay up -d --wait core-replay
    .venv\Scripts\python.exe -m src.replay_core

Replay chỉ cho phép DB local core_replay trên port55435; nạp vào DB trống hoặc kiểm chứng DB đã có, không xóa/ghi đè rows cũ. Hash159 vectors phải khớp c302085913e9a7e86e02c884242f3a073f1fc88aa6e63f933082c7a653589a8e. Test cuối chạy trên bản sao độc lập này; không ghi vào Lab6 gốc.

    $env:DAY6_DATABASE_URL='postgresql://replay:replay_local_only@127.0.0.1:55435/core_replay'
    $env:OPENROUTER_CORE_PROVIDER='wafer'
    $env:PGCONNECT_TIMEOUT='10'
    .venv\Scripts\python.exe -m src.cli preflight

Nếu dùng DB Lab6 gốc cần khởi động container Lab6 tương ứng; adapter chỉ đọc. Không trỏ LAB7_DATABASE_URL vào Lab6. Có thể dừng riêng replay bằng docker compose --profile replay stop core-replay, không xóa volume.

## Bonus rebuild trước freeze

Chạy ở checkout/output/database mới:

    .venv\Scripts\python.exe -m src.cli ingest-bonus --pdf .lab-local/research/wdr2024-full-candidate.pdf --output data/bonus/index
    .venv\Scripts\python.exe -m src.cli index-bonus --chunks data/bonus/index/chunks.jsonl

Raw text/regions tái tạo từ PDF và giữ local. Không ingest/index đè lên experiment đã freeze. Rebuild trên GPU/OS khác có thể tạo fingerprint khác; freeze experiment mới, không sửa hash để giả khớp lượt nộp. Không cam kết byte-identical GPU replay giữa mọi máy.

276 trang đã xử lý,263 trang có text;13 trang thiếu text đã render và là trang trắng (data/bonus/index/blank_page_audit.json).32 table candidates là số vùng thuật toán trích xuất, bao gồm cấu trúc biểu đồ, không khẳng định có32 bảng thực. Có635 source chunks/940 embedding parts.

## Kiểm tra và dev

    .venv\Scripts\python.exe -m unittest discover -s tests -v
    .venv\Scripts\python.exe -m src.cli validate-benchmark --suite core
    .venv\Scripts\python.exe -m src.cli validate-benchmark --suite bonus

Runtime không sửa vector-index manifest; prepared index phải có hash đúng. Core18 dev+8 test release; bonus24 dev+30 test release. Không tune bằng historical tests rồi báo chúng là độc lập.

Ví dụ wrapper một process GPU, dùng output mới:

    $env:API_BUDGET_USD='1.50'
    $env:OMP_NUM_THREADS='1'
    $env:MKL_NUM_THREADS='1'
    $env:TOKENIZERS_PARALLELISM='false'
    $env:HF_ENABLE_PARALLEL_LOADING='false'
    @'
    import torch, sys
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.cuda.set_per_process_memory_fraction(.8)
    sys.argv=['src.cli','dev','--suite','bonus','--config','H2','--output','.lab-local/replay-dev-H2.jsonl']
    from src.cli import main
    main()
    '@ | .venv\Scripts\python.exe -

Đặt dấu đóng here-string ở đầu dòng khi copy vào terminal.80% là allocator cap, không phải utilization cố định. Một embedder CUDA thật được cache cho config chạy tuần tự cùng process. Runner từ chối ghi đè output; kết nối DB có timeout.

CLI trực tiếp không tự đặt giới hạn allocator80%. Trên máy6GB, dùng các thiết lập env/torch của wrapper cho mọi lệnh nạp Qwen, kể cả index-bonus và test. Đổi sys.argv thành các đối số tương ứng, giữ from src.cli import main. Với src.raw_retrieval, đổi cả sys.argv và import sang module đó. Không chạy nhiều process embedding cùng lúc. Các lệnh kiểm tra benchmark/freeze/replay_core không nạp Qwen.

So sánh query gốc không qua LLM rewrite và không có API cost:

    .venv\Scripts\python.exe -m src.raw_retrieval --suite core --output .lab-local/raw-core-replay.json
    .venv\Scripts\python.exe -m src.raw_retrieval --suite bonus --output .lab-local/raw-bonus-replay.json

Báo riêng ranking original-query và pipeline dùng query do model viết lại. ID-exact/source_quote_v1 là diagnostic khác nhau. Metric mới kiểm tra parent/source/page/quote, không phục hồi text chưa gửi model và không thay semantic/visual review.

## Freeze và test

Chọn config bằng dev. Baseline D0 thắng ở core nên baseline/selected dùng chung một run; không nhân đôi mẫu. Với experiment mới, lưu lịch sử manifest cũ và chuẩn bị trạng thái unfrozen rồi:

    .venv\Scripts\python.exe -m src.freeze --suite core --selected D0
    .venv\Scripts\python.exe -m src.freeze --suite bonus --selected H2

Module yêu cầu selection-final.json/comparison-final.json khớp quyết định dev-only. Fingerprint bao gồm source/config/benchmark và live DB; từ chối ghi đè suite đã freeze. Lệnh là src.freeze, không phải src.cli freeze.

Với manifest đi kèm bài, replay sau khi tái tạo đúng inputs/DB và model/provider:

    .venv\Scripts\python.exe -m src.cli test --suite core --config D0 --output .lab-local/core-test-replay.jsonl
    .venv\Scripts\python.exe -m src.cli test --suite bonus --config H2 --output .lab-local/bonus-test-replay.jsonl

Guard từ chối input/model/provider/live DB khác freeze. Replay test đã công bố chỉ để kiểm chứng kỹ thuật, không chọn lượt điểm cao hơn. Nếu sửa theo test cần test mới cho đánh giá độc lập tiếp theo.

Nếu chỉ kiểm tra core, sao lưu root manifest vào .lab-local rồi dùng bản suite riêng để không yêu cầu chuẩn bị corpus bonus:

    New-Item -ItemType Directory -Force .lab-local | Out-Null
    Copy-Item results/run_manifest.json .lab-local/manifest-before-replay.json
    Copy-Item results/core/run_manifest.json results/run_manifest.json

Sau replay khôi phục manifest từ bản sao; results/bonus/run_manifest.json giữ bản manifest cả hai suite. Geometry định vị hình gốc được nộp ở data/bonus/index/region_geometry.json, không chứa bitmap/caption. Sau rebuild, có thể dùng geometry này để đối chiếu bbox; timing và vector fingerprint mới phải được ghi đúng như một replay mới.

## Chi phí và trách nhiệm

HTTP không có usage khóa API. Lệnh python -m src.cli reconcile-unknown-cost tính toàn bộ reservation là upper-bound đã tiêu. Không coi timeout miễn phí hoặc bỏ câu lỗi khỏi mẫu số. Dev bị ngắt/retry được ghi riêng trong evidence/budget record.

Report/nhãn là AI-assisted có đối chiếu nguồn, không khẳng định người học đã tự đọc từng output. Người học chịu trách nhiệm đọc, hiểu/chấp thuận nội dung theo RULES.md, kiểm tra quyền xem repo và tự nộp link theo thông báo lớp. Plans/logs/cache/key/crops không thuộc bộ nộp.
