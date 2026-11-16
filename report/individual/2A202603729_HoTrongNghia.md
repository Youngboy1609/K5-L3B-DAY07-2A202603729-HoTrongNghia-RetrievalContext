# Báo cáo Day7 — Agentic RAG

- Họ và tên: **Hồ Trọng Nghĩa**
- MSSV: **2A202603729**
- Lớp: **L3B**
- Repository: https://github.com/Youngboy1609/K5-L3B-DAY07-2A202603729-HoTrongNghia-RetrievalContext
- Hướng dẫn chạy: [RUN_LAB7.md](../../docs/RUN_LAB7.md).

## Kết quả chính

Phần core đã chọn **D0** trên dev và chạy test release mới: **8/8 câu đạt**, gồm6 câu có đáp án và2 câu thiếu bằng chứng, không có lỗi. D0 đồng thời là baseline và cấu hình được chọn, nên hai vai trò dùng chung một run, không nhân đôi mẫu. Nhãn context/answer/citation được đối chiếu trực tiếp với nguồn tại `results/core/reviews-final.json`.

Bản nộp gốc đạt **23/30 (76,7%)** trên test release cũ. Sau đó đã tạo benchmark v4 mới, chốt pipeline bằng dev rồi chạy một lượt test độc lập: **26/30 (86,7%)**, vẫn dưới ngưỡng27/30; không đề nghị cộng15 điểm bonus. Chi tiết từng câu và lý do ở `results/bonus/test/reviews-v4-A.json`; trace và metrics ở cùng thư mục. Câu tên công ty bị sai chính tả được chấm fail theo quy tắc all-or-nothing; nếu bỏ qua lỗi chính tả thì đạt27/30, nhưng không dùng cách hiểu dễ dãi đó để tuyên bố đạt bonus. Không chạy lại test v4 sau khi xem kết quả. Test cũ được giữ lịch sử; giữa các phiên bản khác nhau không diễn giải chênh lệch điểm thành phép đo cải thiện có kiểm soát.

## Dữ liệu, embedding và benchmark

**Core.** Kế thừa Think Python2e v2.4.1, CC BY-NC3.0, whitelist35 trang vật lý từ Lab6. Snapshot C có159 chunks/vectors, Qwen/Qwen3-Embedding-0.6B revision97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3, CUDA FP16,1024 chiều và normalization. Query dùng instruction prompt query; document không dùng query prompt. Provenance/attribution ở `data/day6_provenance.json`, `data/core/export_manifest.json` và `day6/data/ATTRIBUTION.md`.

Vector store là PostgreSQL16.16/pgvector0.8.7, exact cosine. Adapter Lab6 chỉ đọc. Đã phục hồi159 vectors vào DB replay riêng port55435 và xác nhận hash rows **c302085913e9a7e86e02c884242f3a073f1fc88aa6e63f933082c7a653589a8e**, trùng bản gốc; test core cuối chạy trên bản sao này. Không re-embed hay sửa index Lab6 để lấy điểm Lab7.

**Bonus.** World Bank, World Development Report2024: The Middle-Income Trap, DOI10.1596/978-1-4648-2078-6,276 trang vật lý, source SHA256 trong `data/bonus/manifest.json`. Trích xuất263 trang có text;13 trang còn lại đã render và đều trắng. Có635 source chunks/940 embedding parts.32 table candidates là số vùng detector trích xuất, có cả cấu trúc biểu đồ, không khẳng định có32 bảng thực. Page/region/bbox giữ liên kết về nguồn. PDF/crops giữ local; người chấm truy cập bản gốc qua URL và tái tạo bằng lệnh trong guide. Quyền xử lý tạm thời được người học cho phép; không suy ra quyền tái phân phối các hình của bên thứ ba.

**Agent.** GLM-5.3-Flash qua OpenRouter/Wafer, fallback tắt. Relace có giá thấp hơn trong catalog nhưng các lượt thật gặp HTTP500/usage không rõ; cả bốn cấu hình core cuối cùng được ghim cùng Wafer để so sánh. Quyết định provider có evidence riêng tại `results/runtime/provider-selection.json`.

**Split.** Core18 dev (16+2),8 test release (6+2). Bonus24 dev (20+4),30 test release (24+6), đúng6 table/5 diagram/5 chart/4 multihop/4 text/6 absent. Historical tests được lưu riêng; test release có mục tiêu câu hỏi/đáp án mới. Một số trang/hình được tái sử dụng với câu hỏi khác, được công khai trong `results/bonus/benchmark-release-review.json`. Chọn config bằng dev, không bằng test. Gold/evidence chuẩn chỉ dùng ngoài agent để kiểm tra; runtime chỉ nhận câu hỏi.

## Retrieval và thử nghiệm trên dev

D0=dense trên store Day6; L0=TF-IDF; H1=hybrid reciprocal-rank fusion k60; H2=hybrid với context text lớn hơn. Candidate limit20, tối đa4 search calls/8 model turns. Chapter filter chỉ từ query/tool args, không lấy từ gold. Bộ bảng sau là ranking ở search đầu của agent, có thể dùng query do model viết lại; trace giữ cả câu hỏi gốc và từng query/filter thực.

| Config | Phương pháp | Context tokens | Hit@1 | Evidence@3 | Context Evidence | Dòng có lỗi | Median / API cost |
|---|---|---:|---:|---:|---:|---:|---|
| D0 | Dense | 1800 | 11/16 (68.8%) | 12/16 (75.0%) | 14/16 (87.5%) | 0/18 | 2.93s / $0.00223 |
| L0 | TF-IDF | 1800 | 6/16 (37.5%) | 11/16 (68.8%) | 13/16 (81.2%) | 0/18 | 3.64s / $0.00319 |
| H1 | Hybrid RRF | 1800 | 10/16 (62.5%) | 12/16 (75.0%) | 14/16 (87.5%) | 1/18 | 2.95s / $0.00235 |
| H2 | Hybrid RRF | 4000 | 9/16 (56.2%) | 11/16 (68.8%) | 14/16 (87.5%) | 3/18 | 2.97s / $0.00310 |

D0 được chọn theo quy tắc chốt trước test: Context Evidence cao nhất, rồi ít dòng lỗi, rồi chi phí. Lượt D0 gặp DB unavailable khi Docker khởi động lại được ghi nhận nhưng không dùng so phương pháp; lượt D0 cuối được chạy trên bản replay có hash159 vectors trùng nguồn. Không chọn một lượt tốt hơn trên test. Các biến thể hybrid không được mặc định là tốt hơn baseline.

### Ranking với query gốc

Để tách ảnh hưởng query rewrite khỏi retrieval, đã chạy query gốc trực tiếp trên cùng corpus cho cả bốn config, không gọi API. Context coverage trong bảng này không áp dụng vì không tạo hội thoại model.

| Suite | Config | Hit@1 query gốc | Evidence@3 query gốc |
|---|---|---:|---:|
| core | D0 | 10/16 (62.5%) | 12/16 (75.0%) |
| core | L0 | 7/16 (43.8%) | 11/16 (68.8%) |
| core | H1 | 10/16 (62.5%) | 13/16 (81.2%) |
| core | H2 | 10/16 (62.5%) | 13/16 (81.2%) |
| bonus | D0 | 5/20 (25.0%) | 7/20 (35.0%) |
| bonus | L0 | 9/20 (45.0%) | 8/20 (40.0%) |
| bonus | H1 | 7/20 (35.0%) | 7/20 (35.0%) |
| bonus | H2 | 7/20 (35.0%) | 7/20 (35.0%) |

Chi tiết rank/score/query/filter/timing ở `results/*/dev/raw-query-retrieval.json`. ID-exact là metric lịch sử giữ nguyên. Diagnostic source_quote_v1 bổ sung yêu cầu đúng parent/source/page/quote; không tự chấm đạt sibling cùng parent hoặc khôi phục text chưa gửi model. Diagnostic không thay việc đọc nội dung/ảnh để xác nhận semantic support.

## Agent, context và hai cải thiện

Agent dùng native search và open_region. Registry candidate đã tìm được tách khỏi evidence đã gửi: có thể mở ảnh của ID tìm thấy nhưng chưa pack; chỉ chấp nhận citation khi text hoặc ảnh đã thực sự được cung cấp. Tool chỉ nhận ID, không nhận đường dẫn/bbox do model tự đặt; crop phải nằm trong corpus root và giới hạn kích thước. Mỗi batch tool call có đầy đủ response IDs. Nội dung nguồn và tool là dữ liệu không đáng tin cậy, không phải chỉ dẫn.

**Lỗi dev1 — multi-hop thiếu vế sau.** Trước sửa, search đầu đưa12–14 chunks vào gần hết4.000-token context, các search sau gần như không còn chỗ. Sửa bằng phân bổ allowance theo số search còn lại, trừ shared overhead một lần và loại context lặp. Review source của bốn câu multi-hop dev ghi nhận0/4 ->4/4 đủ cả hai vế. Tuy nhiên test release mới chỉ2/4 multihop đạt; tác động trên dev không bảo đảm tổng quát hóa.

**Lỗi dev2 — chart-04 thiếu citation.** Bản trước trả đúng series màu cam nhưng không có nguồn. Thêm một lượt sửa citation có giới hạn trong8 turns. Nếu vẫn thiếu citation, trả refusal có lỗi thay vì tự thêm ID. Regression đã thấy fail trước sửa/pass sau sửa. Câu chart-04 trong dev cuối đã mở Figure1.2 và trả citation wdr-p068-caption-01. Bộ nhận diện cũng phân biệt refusal rõ ràng để không ép câu thiếu evidence phải tạo citation.

**Lỗi vision.** Trước đây ảnh ở region.image_url nhưng vòng agent đọc sai cấp, làm base64 đi vào tool text. Đã sửa thành image content part, không đưa base64 vào trace/text; smoke có mở ảnh và đối chiếu PDF gốc. Một số metric cũ thấp do source IDs khác child-part IDs; đã giữ bản cũ và bổ sung diagnostic riêng, không đổi nhãn semantic theo ID.

## Đánh giá core test release

Trace `results/core/test/D0-ready.jsonl`, run_id 9939ef0243064a4e948d030846c592d9. Các source passages của6 câu có đáp án đã đọc trực tiếp từ PDF và kiểm tra tại `results/runtime/core-source-audit.json`. Với câu thiếu evidence, kiểm tra toàn selected corpus, không chỉ top-k.

| Config / vai trò | Tool use | Context0/1/2 | Answer0/1/2; mean/2 | Citation hỗ trợ | Câu có citation | Abstention | False abstention |
|---|---|---|---|---|---|---|---|
| D0 baseline = selected, cùng run | 8/8 | 0/0/6 | 0/0/6;2.00/2 | 9/9 | 8/8 | 2/2 | 0/6 |

Sáu câu có đáp án đạt2/2 về context và grounded answer. Hai câu absent được chấm riêng, không đưa vào mẫu số retrieval hay answerable mean. Citation ở refusal chỉ hỗ trợ mô tả nội dung đã truy xuất; không tự chứng minh toàn corpus thiếu một fact. Nhãn/lý do/source pages cho từng câu trong `results/core/reviews-final.json`. Các nhãn core cũ từng sinh bằng keyword/status đã bị rút, không dùng làm điểm cuối.

Core test: Hit@1 5/6 (83.3%), Evidence@3 6/6 (100.0%), Context Evidence 6/6 (100.0%);0 lỗi; median 2.89s; API $0.001504. Baseline/selected trùng nhau nên không tuyên bố mức cải thiện test giữa hai config.

## Bonus: test release mới và giới hạn

Sau sửa, H2 dev đủ24/24,0 lỗi; review chặt23/24, absent4/4 vàmultihop4/4. Một giá trị phụ trong chart-02 được chấm bảo thủ vì làm tròn thô; không đổi gold để qua gate. Một process bị gián đoạn sau8 câu, reservation API mồ côi được tính full upper-bound;16 câu còn lại tiếp tục, giữ8 trace đã hoàn tất. Metadata công khai hai component trong summary.

Pipeline/index/model/benchmark/live DB đã freeze trước một lượt test release30 câu. Gold chuẩn không được đưa vào query/tool. Test bao gồm row/column khác trong TableS.1, đọc legend/diagram, tính chênh lệch từ chart, phối hợp hai trang và factual text. Nhóm diagram dùng3 hình cho5 câu; các chart dùng5 hình khác. Không xem đây là cùng phân phối với v2 cũ.

| Nhóm | Đạt/tổng | Tỷ lệ |
|---|---:|---:|
| table | 5/6 | 83.3% |
| image_diagram | 4/5 | 80.0% |
| chart | 4/5 | 80.0% |
| multihop | 2/4 | 50.0% |
| text | 2/4 | 50.0% |
| unanswerable | 6/6 | 100.0% |
| **Toàn bộ** | **23/30** | **76,7%** |

0 lỗi kỹ thuật; median 6.21s; API $0.018659. Trace/nhãn v3 từng câu tại `results/bonus/test/H2-release.jsonl` và `results/bonus/test/reviews-v3-historical.json`.

Các lỗi còn lại: bỏ lỡ row Malaysia/đoạn managerial delegation/ghi chú RCA; trả category thay cho Type1 trong diagram; đọc nhầm bar2019 sang2020 ở multi-hop; không đủ hop India; một câu đổi nhãn trang vật lý/in thành mâu thuẫn dù ID nguồn và giá trị đúng. Câu cuối được chấm fail theo cách chặt; nếu chấp nhận ID nguồn là đủ thì24/30, vẫn dưới27/30. Câu chart-03 dùng từ people trong câu hỏi nhưng hình đo women; model giữ đúng điều kiện women, được ghi chú như giới hạn wording của benchmark và không sửa câu hỏi sau run.

Không cộng một phần15 điểm bonus. Giữ nguyên test v2 lịch sử20/30 và test release23/30; không tiếp tục chỉnh theo test rồi chạy lại để săn ngưỡng.

### Chạy test v4 đã đóng băng

Sau khi chốt H2 trên dev và đóng băng benchmark/config/index, chạy đủ30 câu với cùng run ID `d2a31948fe514c4193793233ae6dd289`. Kết quả chấm theo ADVANCED.md là **26/30 (86,7%)**, cần27/30; do đó vẫn **không đạt điều kiện bonus**. Có2 lỗi hệ thống (HTTP429 và timeout), đều được giữ trong mẫu số. Median latency5,842ms; API cost theo trace$0.013583. Chi phí ledger toàn chiến dịch **$0.9923434941 / $1.50**, reserved $0; gồm cả reservation upper-bound cho request không rõ chi phí. Record tại `results/runtime/budget-final.json`.

| Nhóm | Đạt/tổng |
|---|---:|
| table | 5/6 |
| image_diagram | 4/5 |
| chart | 5/5 |
| multihop | 2/4 |
| text | 4/4 |
| unanswerable | 6/6 |
| **Toàn bộ** | **26/30 (86,7%)** |

Hai lỗi kỹ thuật là Mexico energy-intensity (HTTP429) và multi-hop Korea (timeout). Multi-hop Türkiye có đúng GNI nhưng không trả lời được fiscal target, nên fail. Câu Figure O.6 có typo tên pháp nhân (“Electroic” thay cho “Electric”); chấm fail nghiêm theo all-or-nothing. Nếu người chấm bỏ qua lỗi này như typo thì thành27/30, nhưng không tuyên bố đạt bonus theo cách chấm dễ dãi. Nhãn/lý do từng câu và source page ở `results/bonus/test/reviews-v4-A.json`; bảng metrics ở `results/bonus/test/metrics-v4-A.json`; benchmark và overlap audit ở `benchmark/bonus/questions-v4-review.md`.

Không dùng test v4 để sửa pipeline và không chạy thêm lượt test. V3 test 23/30 được giữ làm kết quả lịch sử; vì câu hỏi test đã thay đổi, không xem chênh lệch 23 lên26 là phép đo cải thiện có kiểm soát.

## Tái lập, chi phí và kiểm tra nộp

Code/dependencies được ghim trong requirements; regression **61 tests đạt**, pip check đạt. Có negative tests từ chối DB/provider khác freeze. Live DB và file fingerprints được kiểm tra trước test. Runtime không tự ghi lại index manifest trong lúc đánh giá. .gitattributes giữ byte để fingerprint không đổi do Git newline conversion. Nguồn Lab6 gốc được giữ; replay DB riêng đã chứng minh khớp rows.

Đã gặp Windows native exception c10.dll0xc0000005 lúc nạp model và một lượt bị treo do Docker tắt. Chạy một model/process, CPU thread1, allocator0.8 và DB connect timeout10 giây giúp giới hạn tài nguyên/chờ; các lượt cuối đã hoàn tất, không diễn giải đó là chứng minh đã chữa mọi nguyên nhân native crash.

Tổng ledger cuối **$0.9923434941 / $1.50**, reserved $0; có tính các lượt dev/test lịch sử, lỗi HTTP và orphan reservation theo upper-bound. Chi phí embedding local không phải API cost, nhưng vẫn tốn thời gian/tài nguyên máy. Số liệu billing cuối trên tài khoản có thể thấp hơn phần upper-bound đã dự phòng. Record: `results/runtime/budget-final.json`.

Báo cáo và nhãn là AI-assisted, đã đối chiếu nguồn; không giả xác nhận người học đã tự đọc mọi output. Tôi chịu trách nhiệm hiểu/kiểm tra nội dung nộp theo RULES.md. Tài liệu đề README/RULES/RUBRIC/SUBMISSION được giữ nguyên; implementation guide nằm riêng. Không đưa plans/local logs/venv/weights/.env/PDF-crop bonus vào bộ nộp.

## Nguồn và artifact chính

- Think Python2e/CC BY-NC3.0: `day6/data/ATTRIBUTION.md` và provenance Lab6.
- World Bank2024, The Middle-Income Trap: https://doi.org/10.1596/978-1-4648-2078-6; URL truy cập và attribution trong `data/bonus/manifest.json`.
- Quy tắc chấm: RUBRIC.md, BENCHMARK.md, ADVANCED.md.
- Code/commands: `src/`, `configs/`, `requirements.txt`, [RUN_LAB7.md](../../docs/RUN_LAB7.md).
- Quyết định dev: `results/core/selection-final.json`, `results/bonus/selection-final.json`.
- Freeze: `results/run_manifest.json`; core/bonus final traces, grades và metrics nằm trong các thư mục tương ứng.
