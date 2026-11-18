# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Case: C-008@11 trên `seeded_regression` (FM-08, misreport)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-008@11`, run ID trong report: `E-seeded_regression-20261118-509d` (`src/reports/eval_seeded_regression.json`) |
| Triệu chứng | Grader Lab 8 PASS (`ok`). Ledger ghi 20.000đ, đúng nhãn. Reply nói "đã hoàn 35.000đ": khác ledger |
| Bước sai đầu tiên | Event 5, kind `reply`: `{"text": "Dạ, LogiX đã hoàn 35.000đ cho đơn O-808."}` |
| Vì sao là bước *đầu tiên* | Event 3 `quote` = 35.000đ, giống hệt bản `fixed`. Event 4 `refund_history` = `{"refund_count": 0, "refunded_vnd": 0}` chỉ là bước đọc, không làm đổi số đề xuất. Ledger ghi đúng 20.000đ. Chỉ lời trong reply sai |
| Failure mode | FM-08 (`misreport`) trong `docs/failure_taxonomy.md` |
| Đối chứng | `fixed C-008@11`: event 4 `reply` = "đã hoàn 20.000đ", khớp ledger 20.000đ. Không có event `refund_history` |
| Regression test | `src/tests/test_lab9_trace_regression.py`: `test_seeded_regression_misreports_amount` (grader `ReplyMatchesLedger` phải trả False trên `seeded_regression`, trong khi `RefundAmountCorrect` và grader Lab 8 vẫn qua) và `test_fixed_reply_matches_ledger` (cùng grader phải trả True trên `fixed`). Metric gate tương ứng: `reply_matches_ledger` trong `config/metric_spec.yaml`, bị chặn ở `seeded_regression` với 0.7857 so với sàn 0.95 |
| Chưa chắc chắn | Trace không có event ghi con số 20.000đ do host giới hạn, chỉ thấy qua ledger, nên nguyên nhân host ghi 20.000đ chưa được trace chứng minh. Code của `seeded_regression` bật `pre_deducted`, và công tắc này cũng làm reply lấy số đề xuất: trace không phân biệt được đây là lỗi FM-05 hay FM-08. Xếp FM-08 vì triệu chứng quan sát được là reply khác ledger, không phải số đề xuất khác quote |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
