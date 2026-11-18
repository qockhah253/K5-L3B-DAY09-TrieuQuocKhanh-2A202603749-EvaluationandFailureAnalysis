# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt (tp 24, fp 4, fn 6, tn 66; tỉ lệ FAIL quan sát 0.28, hiệu chỉnh Rogan-Gladen 0.30) | dùng |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không đạt: κ và recall dưới ngưỡng (tp 9, fp 0, fn 21, tn 70; tỉ lệ FAIL quan sát 0.09, hiệu chỉnh 0.30) | loại |

## ≥5 case audit thủ công (tiêu chí tone_ok)
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | H-008 "Em đã hoàn tiền cho anh rồi nha, anh check giúp em." | PASS | FAIL | Người | Xưng "em" + "nha" quá suồng sã với khách khiếu nại. Judge coi là thân thiện: bỏ sót lỗi giọng điệu |
| 2 | H-017 "Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha." | PASS | FAIL | Người | Gọi khách là "bạn". Cùng kiểu lỗi với #1: judge dễ dãi với từ xưng hô thân mật |
| 3 | H-029 "Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm." | PASS | FAIL | Người | Giọng ra lệnh ("không cần nhắn thêm"). Judge chỉ thấy "Dạ, vui lòng" ở đầu câu |
| 4 | H-042 "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." | FAIL | PASS | Người | Reply ngắn nhưng đủ ý. Judge phạt vì "thiếu xin lỗi", tiêu chí này không bắt buộc khi đã hoàn tiền thành công |
| 5 | H-051 "Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ." | FAIL | PASS | Người | Từ "refund" được CS LogiX cho phép. Judge phạt vì tiếng Anh: báo động nhầm |
| 6 | H-081 "Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ." | FAIL | PASS | Judge | Cột `note` ghi nhãn người đọc nhầm ticket. Đây là lỗi nhãn của người, cần sửa nhãn thay vì sửa judge |

## Kết luận
- Tiêu chí bị loại: `helpful`. Ma trận nhầm lẫn tp 9, fp 0, fn 21, tn 70: recall 0.30 (ngưỡng 0.70), κ 0.375 (ngưỡng 0.60). Judge bỏ lọt 21 trên 30 ca FAIL, phần lớn là reply nói số tiền khác ledger (ví dụ HL-015 nói 55.000đ, ledger 40.000đ) hoặc giọng thiếu lịch sự ("Ok bạn ... nhé"). Lỗi số tiền (FM-08) phải chấm bằng code so reply với ledger, không giao cho judge.
- Tiêu chí dùng: `tone_ok`. Judge hơi dễ dãi với xưng hô thân mật (ca #1, #2, #3) và hơi khắt khe với việc "thiếu xin lỗi" hoặc từ tiếng Anh (ca #4, #5). Dùng được cho giám sát giọng điệu, không dùng để chặn merge.
- Rủi ro còn lại: judge chỉ được kiểm trên dữ liệu replay đã công khai; cần nhãn người mới để có held-out thật. Ca #6 cho thấy nhãn người cũng có thể sai (1 trong 10 bất đồng), nên κ bị đo thấp hơn thực tế một chút.
