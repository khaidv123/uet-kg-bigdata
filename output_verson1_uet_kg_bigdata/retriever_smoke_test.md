# Hybrid Query Report

- Timestamp: 2026-04-07T22:46:54.097320
- Query: Đơn vị đào tạo có trách nhiệm gì khi phát hiện ra việc sử dụng thông tin không chính xác trong quá trình đăng ký tuyển sinh?
- Mode: hybrid
- Working dir: D:\projects\vnu_qa\rag_rl\create_references\test\output_verson1_prestop_backup\rag_storage

## Answer

Theo quy định về trách nhiệm của **đơn vị đào tạo**, trong công tác tuyển sinh (bao gồm việc cung cấp và xử lý thông tin liên quan đến xét tuyển), đơn vị đào tạo có các trách nhiệm sau khi phát hiện thông tin **không chính xác** trong quá trình đăng ký/tuyển sinh:

- **Bảo đảm tính xác thực của thông tin, dữ liệu tuyển sinh** mà đơn vị cung cấp và/hoặc đưa lên hệ thống theo hướng dẫn của Bộ GD&ĐT: đơn vị đào tạo phải cung cấp “đầy đủ, đúng định dạng và bảo đảm tính xác thực” của thông tin/dữ liệu tuyển sinh lên hệ thống.  
- **Không để thí sinh đăng ký dự tuyển khi chưa đủ điều kiện**: đơn vị đào tạo phải cung cấp đầy đủ thông tin, tư vấn và hướng dẫn thí sinh, “không để thí sinh đăng ký” vào nhóm ngành/ngành/chương trình/phương thức tuyển sinh của đơn vị mà **không đủ điều kiện**.  
- **Kiểm tra thông tin và hồ sơ minh chứng** tại giai đoạn nhập học: đơn vị đào tạo phải kiểm tra thông tin và hồ sơ minh chứng khi thí sinh nhập học, bảo đảm các thí sinh nhập học “phải đủ điều kiện trúng tuyển”.

Ngoài ra, đơn vị đào tạo còn phải **giải quyết các đơn thư phản ánh, khiếu nại, tố cáo** liên quan đến công tác xét tuyển của đơn vị theo quy định của pháp luật.

### References

* [1] ..\..\data\quyet_dinh_1328_chunks.json

## Retrieval Summary

- Entities: 10
- Relationships: 42
- Chunks: 12
- References: 0

## Entities

```json
[
  {
    "entity_name": "Các đơn vị đào tạo",
    "entity_type": "đơn_vị_trực_thuộc",
    "description": "Các đơn vị đào tạo được đề cập như chủ thể tuyển sinh, nơi thí sinh tìm hiểu thông tin tuyển sinh.",
    "source_id": "chunk-bf836ea6db4d8badfb97990a59aa4543",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485431
  },
  {
    "entity_name": "Thông tin, Tư vấn và Hướng dẫn Thí sinh",
    "entity_type": "method",
    "description": "Nội dung cung cấp đầy đủ thông tin, tư vấn và hướng dẫn thí sinh để thí sinh không đăng ký dự tuyển khi chưa đủ điều kiện.",
    "source_id": "chunk-1cb8513b18d53e7800fe51928b1efe1c",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485439
  },
  {
    "entity_name": "đơn vị đào tạo",
    "entity_type": "đơn_vị_trực_thuộc",
    "description": "đơn vị đào tạo là chủ thể phối hợp triển khai các quy trình đăng ký, tổ chức xét tuyển, xử lý nguyện vọng và xác nhận nhập học.<SEP>đơn vị đào tạo là chủ thể có thể quy định cụ thể về đối tượng, điều kiện dự tuyển cho mỗi phương thức tuyển sinh.",
    "source_id": "chunk-42c0bd7eac70305a81f43b3e9300d670<SEP>chunk-c0d3f2c39bc7c8e37aab19434ceb8862",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485329
  },
  {
    "entity_name": "Đơn vị Đào tạo",
    "entity_type": "đơn_vị_trực_thuộc",
    "description": "Đơn vị đào tạo tải lên hệ thống danh sách thí sinh dự kiến đủ điều kiện trúng tuyển, lặp lại quy trình xét tuyển ở chu kỳ sau và quyết định điểm trúng tuyển ở chu kỳ cuối.<SEP>Đơn vị đào tạo được nêu như chủ thể thực hiện các nghĩa vụ trong công tác xét tuyển theo đề án tuyển sinh đã công bố và theo quy định pháp luật.<SEP>Đơn vị đào tạo thực hiện công bố kế hoạch xét tuyển, hướng dẫn đăng ký, công bố điểm trúng tuyển và điều kiện, tiêu chí phụ (nếu có), cũng như tổ chức cho thí sinh tra cứu kết quả.<SEP>Tổ chức thực hiện xác nhận nhập học và có thể cho phép thí sinh tham gia xét tuyển ở nơi khác hoặc ở đợt bổ sung.",
    "source_id": "chunk-ca3d17d3c1f7fff2b4d41619bb94314f<SEP>chunk-1cb8513b18d53e7800fe51928b1efe1c<SEP>chunk-cf425f7ca685593f88901f2f6d924893<SEP>chunk-1f39a0ff78c35fa4b16ff781cf5edaf3",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485931
  },
  {
    "entity_name": "Minh Bạch Thông Tin",
    "entity_type": "concept",
    "description": "Đơn vị đào tạo có trách nhiệm công bố thông tin tuyển sinh đầy đủ, rõ ràng và kịp thời qua các phương tiện truyền thông phù hợp để xã hội, cơ quan quản lý nhà nước và ĐHQGHN cùng giám sát.",
    "source_id": "chunk-6bfc5f2ad22b00d8a493668fdba2fd14",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775486113
  },
  {
    "entity_name": "đăng ký dự tuyển",
    "entity_type": "method",
    "description": "Hoạt động đăng ký dự tuyển của thí sinh thuộc đối tượng xét tuyển thẳng, thực hiện trực tuyến hoặc trực tiếp tại đơn vị đào tạo.",
    "source_id": "chunk-4b93cbd5d0914f2cef5a210a16b4bbf5",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775486301
  },
  {
    "entity_name": "Đơn Vị Đào Tạo",
    "entity_type": "đơn_vị_trực_thuộc",
    "description": "Đơn Vị Đào Tạo tổ chức xét tuyển theo các phương thức và tiêu chí riêng hoặc phối hợp theo nhóm để tổ chức xét tuyển theo phương thức và tiêu chí chung.<SEP>Đơn vị đào tạo là lựa chọn về nơi học tập, được thể hiện kèm mã trường trong phần lựa chọn đơn vị đào tạo.<SEP>Đơn vị đào tạo là nơi có dữ liệu trúng tuyển và nhập học được hệ thống hỗ trợ tuyển sinh chung quản lý.<SEP>Đơn vị đào tạo được nêu là chủ thể căn cứ kết quả học tập THPT và yêu cầu ngành đào tạo để quyết định nhận thí sinh vào học.<SEP>Đơn vị đào tạo tham gia tuyển sinh và có các trách nhiệm như hợp tác bình đẳng, cạnh tranh lành mạnh, công bố thông tin tuyển sinh minh bạch và báo cáo/giải trình theo yêu cầu của ĐHQGHN và cơ quan quản lý nhà nước.",
    "source_id": "chunk-1b5dfa8d570d9f115a0abdcc7e2ecb66<SEP>chunk-81d92fffe062e7c8fcbd0316fa088c66<SEP>chunk-170b153fd5ea4a9ddacf6c3b10783810<SEP>chunk-e2e77743fb90d76576cdd797d7c3d1da<SEP>chunk-6bfc5f2ad22b00d8a493668fdba2fd14",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775486117
  },
  {
    "entity_name": "các đơn vị đào tạo",
    "entity_type": "đơn_vị_trực_thuộc",
    "description": "các đơn vị đào tạo có đại diện tham gia thành phần Ban Chỉ đạo tuyển sinh.<SEP>các đơn vị đào tạo thực hiện quyền tự chủ, trách nhiệm giải trình và các biện pháp bảo đảm điều kiện tuyển sinh.",
    "source_id": "chunk-dccd9d905892f60251e114b78ae49b4c<SEP>chunk-0abf0789ba93e1147b98fac10073dd1f",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485842
  },
  {
    "entity_name": "Đơn vị đào tạo",
    "entity_type": "đơn_vị_trực_thuộc",
    "description": "Đơn vị đào tạo là chủ thể thực hiện các nội dung liên quan đến tuyển sinh và đào tạo theo quy định, bao gồm việc tổ chức thông báo tuyển sinh và công bố đề án tuyển sinh trước khi mở đăng ký dự tuyển. Trên cơ sở các nguyên tắc chung được nêu và công khai trong đề án tuyển sinh, đơn vị đào tạo thực hiện quy đổi theo các quy định cụ thể, triển khai các biện pháp cần thiết để phục vụ thí sinh. Trong quá trình tuyển sinh, Đơn vị đào tạo quyết định danh sách thí sinh trúng tuyển theo từng nhóm ngành/ngành và theo từng chương trình đào tạo, công bố điểm trúng tuyển; nếu có quy định thì đồng thời công bố các điều kiện/tiêu chí phụ kèm theo, các hình thức ưu tiên xét tuyển cho từng trường hợp và xác định nhóm ngành/ngành hoặc chương trình mà các đối tượng tuyển thẳng được vào theo quy định. Cuối cùng, đơn vị đào tạo chịu trách nhiệm tổ chức triển khai toàn bộ công tác tuyển sinh đúng với nội dung trong thông báo tuyển sinh và đề án tuyển sinh.\n\nĐơn vị đào tạo có thể gắn với các trường đại học thành viên và các trường/khoa trực thuộc ĐHQGHN (những đơn vị có chức năng, nhiệm vụ tổ chức đào tạo đại học). Đơn vị đào tạo sử dụng mã số quy ước thống nhất để định danh nhóm ngành/ngành hoặc chương trình đào tạo và áp dụng phương thức tuyển sinh. Ở giai đoạn hậu tuyển, Đơn vị đào tạo gửi giấy báo trúng tuyển, hướng dẫn thủ tục nhập học và xem xét tiếp nhận hoặc bảo lưu kết quả tuyển sinh khi thí sinh không xác nhận nhập học; đồng thời phải giải trình về căn cứ khoa học và thực tiễn trong việc xác định phương thức tuyển sinh, phương thức xét tuyển, tổ hợp xét tuyển và phân bổ chỉ tiêu tuyển sinh. Đơn vị đào tạo cũng thực hiện cam kết, tư vấn, hỗ trợ và giải quyết khiếu nại để bảo vệ quyền lợi của thí sinh, đặc biệt tổ chức cho thí sinh thuộc đối tượng xét tuyển thẳng đăng ký dự tuyển và tổ chức xét tuyển thẳng cho các thí sinh đủ điều kiện; có kế hoạch và thông báo xét tuyển sớm, tổ chức xét tuyển cho thí sinh đã hoàn thành thủ tục dự tuyển, và công bố/tải danh sách thí sinh đủ điều kiện trúng tuyển lên hệ thống.\n\nVề tổ chức, Đơn vị đào tạo là nơi có Thủ trưởng thành lập HĐTS và chịu trách nhiệm tổ chức, điều hành toàn bộ công tác tuyển sinh theo quy định. Nếu Đơn vị đào tạo vi phạm về công tác tuyển sinh thì sẽ bị áp dụng xử lý theo quy định của ĐHQGHN và các quy định pháp luật hiện hành.",
    "source_id": "chunk-ddace097418fed36cbe37da8f4249576<SEP>chunk-3f8b3d332cf0c347e8de3d57dc270374<SEP>chunk-c214b57125a6e684d66bb9c16816dffa<SEP>chunk-0d6008bd889a0ebc91d42d3a06f83f83<SEP>chunk-ffb1cfd0c23e7fa4206abe42c582cc74<SEP>chunk-73e274f4a5ed1f38ed08014e717a6f92<SEP>chunk-d830f682b07ebeb668d54551a6209b96<SEP>chunk-ff59c46f3ab103315ca32379f39a3d18<SEP>chunk-18679ecca078f74da86923a647f33b04<SEP>chunk-39701be07619a29470685a24ef242d87<SEP>chunk-d847432d893deb66ba9545e43db1c0ff<SEP>chunk-c482f693ef8c5985db5d7021905a1633<SEP>chunk-34684aec0d79f3237acdda225af3e906<SEP>chunk-4b93cbd5d0914f2cef5a210a16b4bbf5<SEP>chunk-759233ad94ecba2518607c2566ed9fbe<SEP>chunk-d70df8c903fddbcbfa9aedc2b549731f<SEP>chunk-04f0fde7624010888d30f43632b7cf85",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775486854
  },
  {
    "entity_name": "Đơn vị đào tạo thông báo tuyển sinh",
    "entity_type": "event",
    "description": "Hành vi thông báo tuyển sinh của đơn vị đào tạo, đi kèm việc công bố đề án tuyển sinh trước khi mở đăng ký dự tuyển của đợt tuyển sinh đầu tiên.",
    "source_id": "chunk-73e274f4a5ed1f38ed08014e717a6f92",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485471
  }
]
```

## Relationships

```json
[
  {
    "src_id": "ĐHQGHN",
    "tgt_id": "Đơn vị đào tạo",
    "description": "Đơn vị đào tạo báo cáo ĐHQGHN kết quả xét tuyển thẳng trước khi công bố kết quả theo kế hoạch chung.<SEP>Đơn vị đào tạo vi phạm về tuyển sinh bị áp dụng xử lý theo quy định của ĐHQGHN.",
    "keywords": "báo cáo,căn cứ xử lý,phê duyệt theo kế hoạch,quy định",
    "weight": 2.0,
    "source_id": "chunk-4b93cbd5d0914f2cef5a210a16b4bbf5<SEP>chunk-759233ad94ecba2518607c2566ed9fbe",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775486501
  },
  {
    "src_id": "Thông tin, Tư vấn và Hướng dẫn Thí sinh",
    "tgt_id": "Đơn vị Đào tạo",
    "description": "Đơn vị đào tạo phải cung cấp đầy đủ thông tin, tư vấn và hướng dẫn thí sinh để tránh việc đăng ký dự tuyển khi không đủ điều kiện.",
    "keywords": "trách nhiệm hỗ trợ,điều kiện đăng ký",
    "weight": 1.0,
    "source_id": "chunk-1cb8513b18d53e7800fe51928b1efe1c",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485493
  },
  {
    "src_id": "Minh Bạch Thông Tin",
    "tgt_id": "ĐHQGHN",
    "description": "Minh bạch thông tin tuyển sinh được thực hiện để ĐHQGHN cùng giám sát.",
    "keywords": "giám sát,thông tin tuyển sinh",
    "weight": 1.0,
    "source_id": "chunk-6bfc5f2ad22b00d8a493668fdba2fd14",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775486196
  },
  {
    "src_id": "Minh Bạch Thông Tin",
    "tgt_id": "Đơn Vị Đào Tạo",
    "description": "Đơn vị đào tạo có trách nhiệm công bố thông tin tuyển sinh đầy đủ, rõ ràng và kịp thời để xã hội, cơ quan quản lý nhà nước và ĐHQGHN cùng giám sát.",
    "keywords": "công bố thông tin,giám sát",
    "weight": 1.0,
    "source_id": "chunk-6bfc5f2ad22b00d8a493668fdba2fd14",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775486188
  },
  {
    "src_id": "Thí sinh",
    "tgt_id": "Đơn vị đào tạo",
    "description": "Đơn vị đào tạo tổ chức xét tuyển cho những thí sinh đã hoàn thành thủ tục dự tuyển.",
    "keywords": "tổ chức xét tuyển",
    "weight": 1.0,
    "source_id": "chunk-d70df8c903fddbcbfa9aedc2b549731f",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775486721
  },
  {
    "src_id": "Đơn vị đào tạo",
    "tgt_id": "Đơn vị đào tạo thông báo tuyển sinh",
    "description": "Đơn vị đào tạo thực hiện việc thông báo tuyển sinh theo yêu cầu của quy định.",
    "keywords": "hành động,trách nhiệm",
    "weight": 1.0,
    "source_id": "chunk-73e274f4a5ed1f38ed08014e717a6f92",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485533
  },
  {
    "src_id": "Đơn vị đào tạo",
    "tgt_id": "Đề án tuyển sinh",
    "description": "Đơn vị đào tạo công bố công khai nguyên tắc quy đổi cụ thể trong Đề án tuyển sinh.<SEP>Đơn vị đào tạo xây dựng, công bố và thực hiện đề án tuyển sinh.",
    "keywords": "công bố,trách nhiệm,văn bản công khai,xây dựng và thực hiện",
    "weight": 2.0,
    "source_id": "chunk-ddace097418fed36cbe37da8f4249576<SEP>chunk-ffb1cfd0c23e7fa4206abe42c582cc74",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485511
  },
  {
    "src_id": "Bộ GD&ĐT",
    "tgt_id": "Trách nhiệm của đơn vị đào tạo",
    "description": "Đơn vị đào tạo phải thực hiện việc cung cấp thông tin/dữ liệu tuyển sinh lên hệ thống theo hướng dẫn của Bộ GD&ĐT.",
    "keywords": "quy trình dữ liệu,tuân thủ hướng dẫn",
    "weight": 1.0,
    "source_id": "chunk-bf836ea6db4d8badfb97990a59aa4543",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485485
  },
  {
    "src_id": "HĐTS",
    "tgt_id": "Đơn vị đào tạo",
    "description": "Đơn vị đào tạo có HĐTS được thành lập để tổ chức và điều hành công tác tuyển sinh.",
    "keywords": "cấu phần tuyển sinh,quản lý",
    "weight": 1.0,
    "source_id": "chunk-04f0fde7624010888d30f43632b7cf85",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775486982
  },
  {
    "src_id": "Các đơn vị đào tạo",
    "tgt_id": "Trách nhiệm của thí sinh",
    "description": "Thí sinh phải tìm hiểu thông tin tuyển sinh do các đơn vị đào tạo công bố.",
    "keywords": "tìm hiểu thông tin,đối tượng tuyển sinh",
    "weight": 1.0,
    "source_id": "chunk-bf836ea6db4d8badfb97990a59aa4543",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485474
  },
  {
    "src_id": "Chương trình đào tạo",
    "tgt_id": "Ngôn ngữ đào tạo",
    "description": "Đề án tuyển sinh nêu thông tin về ngôn ngữ đào tạo.",
    "keywords": "ngôn ngữ,thông tin liên quan",
    "weight": 1.0,
    "source_id": "chunk-ffb1cfd0c23e7fa4206abe42c582cc74",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485521
  },
  {
    "src_id": "Thông tin tuyển sinh",
    "tgt_id": "Trách nhiệm của thí sinh",
    "description": "Thí sinh có trách nhiệm tìm hiểu kỹ thông tin tuyển sinh của các đơn vị đào tạo và chỉ đăng ký nguyện vọng phù hợp điều kiện.",
    "keywords": "nghĩa vụ tìm hiểu,đăng ký đúng điều kiện",
    "weight": 1.0,
    "source_id": "chunk-bf836ea6db4d8badfb97990a59aa4543",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485469
  },
  {
    "src_id": "Bộ GD&ĐT",
    "tgt_id": "Đơn Vị",
    "description": "Đơn vị đào tạo thực hiện lưu trữ, bảo quản tài liệu theo các quy định do Bộ GD&ĐT ban hành.",
    "keywords": "trách nhiệm,tuân thủ quy định",
    "weight": 1.0,
    "source_id": "chunk-99f0cf87ddf1406829eba421dbb9a9cc",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775486481
  },
  {
    "src_id": "Giá trị thông tin, dữ liệu cần thiết",
    "tgt_id": "Trách nhiệm của thí sinh",
    "description": "Thí sinh đồng ý để đơn vị đào tạo sử dụng thông tin/dữ liệu cần thiết phục vụ công tác xét tuyển.",
    "keywords": "phục vụ xét tuyển,đồng ý sử dụng dữ liệu",
    "weight": 1.0,
    "source_id": "chunk-bf836ea6db4d8badfb97990a59aa4543",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485494
  },
  {
    "src_id": "Mức điểm ưu tiên",
    "tgt_id": "Đơn vị đào tạo",
    "description": "Đơn vị đào tạo quy đổi cụ thể mức điểm ưu tiên theo nguyên tắc chung và công bố công khai trong Đề án tuyển sinh.",
    "keywords": "công bố,quy đổi",
    "weight": 1.0,
    "source_id": "chunk-ddace097418fed36cbe37da8f4249576",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485085
  },
  {
    "src_id": "công tác tuyển sinh",
    "tgt_id": "Đơn vị đào tạo",
    "description": "Quy định nêu đơn vị đào tạo vi phạm về công tác tuyển sinh và chịu xử lý theo mức độ.",
    "keywords": "hoạt động,phạm vi vi phạm",
    "weight": 1.0,
    "source_id": "chunk-759233ad94ecba2518607c2566ed9fbe",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775486493
  },
  {
    "src_id": "Chuẩn bị điều kiện tham gia dự tuyển và thực hiện các bước theo kế hoạch tuyển sinh",
    "tgt_id": "Thí sinh",
    "description": "Thí sinh dùng thông tin từ đề án tuyển sinh để chuẩn bị điều kiện dự tuyển và thực hiện các bước theo kế hoạch tuyển sinh.",
    "keywords": "chuẩn bị,thực hiện kế hoạch",
    "weight": 1.0,
    "source_id": "chunk-ffb1cfd0c23e7fa4206abe42c582cc74",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485517
  },
  {
    "src_id": "Hệ thống",
    "tgt_id": "Trách nhiệm của đơn vị đào tạo",
    "description": "Đơn vị đào tạo phải cung cấp đầy đủ, đúng định dạng và bảo đảm tính xác thực thông tin, dữ liệu tuyển sinh lên hệ thống theo hướng dẫn.",
    "keywords": "cung cấp dữ liệu,tuân thủ định dạng",
    "weight": 1.0,
    "source_id": "chunk-bf836ea6db4d8badfb97990a59aa4543",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485483
  },
  {
    "src_id": "Đơn vị đào tạo",
    "tgt_id": "Ưu tiên xét tuyển",
    "description": "Đơn vị đào tạo quy định hình thức ưu tiên xét tuyển khác đối với các nhóm thí sinh được nêu.",
    "keywords": "hình thức ưu tiên,quy định áp dụng",
    "weight": 1.0,
    "source_id": "chunk-d830f682b07ebeb668d54551a6209b96",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485727
  },
  {
    "src_id": "Thí sinh Chưa Trúng tuyển hoặc Chưa Xác nhận Nhập học",
    "tgt_id": "Đơn vị Đào tạo",
    "description": "Thí sinh đăng ký xét tuyển đợt bổ sung theo kế hoạch và hướng dẫn của đơn vị đào tạo.",
    "keywords": "hướng dẫn,đăng ký theo kế hoạch",
    "weight": 1.0,
    "source_id": "chunk-cf425f7ca685593f88901f2f6d924893",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485565
  },
  {
    "src_id": "Phương thức tuyển sinh",
    "tgt_id": "Đơn vị đào tạo",
    "description": "Đơn vị đào tạo thông báo xét tuyển sớm đối với một số phương thức tuyển sinh.",
    "keywords": "thực hiện xét tuyển theo phương thức",
    "weight": 1.0,
    "source_id": "chunk-d70df8c903fddbcbfa9aedc2b549731f",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775486709
  },
  {
    "src_id": "Chế Độ Lưu Trữ",
    "tgt_id": "Đơn Vị",
    "description": "Đơn vị đào tạo chịu trách nhiệm thực hiện chế độ lưu trữ đối với tài liệu liên quan tuyển sinh.",
    "keywords": "quản lý hồ sơ,trách nhiệm",
    "weight": 1.0,
    "source_id": "chunk-99f0cf87ddf1406829eba421dbb9a9cc",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775486485
  },
  {
    "src_id": "Danh sách thí sinh trúng tuyển",
    "tgt_id": "Đơn vị đào tạo",
    "description": "Đơn vị đào tạo quyết định danh sách thí sinh trúng tuyển vào các nhóm ngành/ngành và chương trình đào tạo.",
    "keywords": "phân bổ vào,quyết định",
    "weight": 1.0,
    "source_id": "chunk-3f8b3d332cf0c347e8de3d57dc270374",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485141
  },
  {
    "src_id": "Đơn vị đào tạo",
    "tgt_id": "đăng ký dự tuyển",
    "description": "Đơn vị đào tạo tổ chức cho thí sinh thực hiện đăng ký dự tuyển theo điều khoản.",
    "keywords": "thủ tục,triển khai",
    "weight": 1.0,
    "source_id": "chunk-4b93cbd5d0914f2cef5a210a16b4bbf5",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775486327
  },
  {
    "src_id": "Các Chứng Chỉ Ngoại Ngữ Đáp Ứng Điều Kiện Chuẩn Đầu Ra",
    "tgt_id": "Phòng Đào Tạo (P.ĐT)",
    "description": "Phòng Đào tạo gửi thông tin tới các đơn vị và sinh viên về các chứng chỉ ngoại ngữ (tiếng Anh) đáp ứng chuẩn đầu ra.",
    "keywords": "truyền đạt thông tin",
    "weight": 1.0,
    "source_id": "chunk-1a3df01c18894f70ba1089c4742063c5",
    "file_path": "..\\..\\data\\data_1000_chunk_512.json",
    "created_at": 1775554198
  },
  {
    "src_id": "Công bố điểm trúng tuyển",
    "tgt_id": "Đơn vị đào tạo",
    "description": "Đơn vị đào tạo công bố điểm trúng tuyển (và các điều kiện, tiêu chí phụ nếu có).",
    "keywords": "công bố thông tin",
    "weight": 1.0,
    "source_id": "chunk-3f8b3d332cf0c347e8de3d57dc270374",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485143
  },
  {
    "src_id": "Trách Nhiệm Giải Trình",
    "tgt_id": "Đơn Vị Đào Tạo",
    "description": "Đơn vị đào tạo có trách nhiệm báo cáo theo yêu cầu của ĐHQGHN, các cơ quan quản lý nhà nước và giải trình với xã hội về các vấn đề lớn gây bức xúc cho người dân.",
    "keywords": "báo cáo,giải trình",
    "weight": 1.0,
    "source_id": "chunk-6bfc5f2ad22b00d8a493668fdba2fd14",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775486196
  },
  {
    "src_id": "Điều 2",
    "tgt_id": "Đơn vị đào tạo",
    "description": "Điều 2 giải thích khái niệm “Đơn vị đào tạo”.",
    "keywords": "giải thích từ ngữ,định nghĩa",
    "weight": 1.0,
    "source_id": "chunk-39701be07619a29470685a24ef242d87",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485786
  },
  {
    "src_id": "Chế độ báo cáo",
    "tgt_id": "Quy định, quy trình (nếu có) và các văn bản hướng dẫn tuyển sinh của đơn vị đào tạo",
    "description": "Chế độ báo cáo yêu cầu gửi nhóm tài liệu quy định, quy trình và văn bản hướng dẫn tuyển sinh của đơn vị đào tạo.",
    "keywords": "thành phần hồ sơ,tài liệu hướng dẫn",
    "weight": 1.0,
    "source_id": "chunk-5ef7502b5fff13cfaf706ccf8f094af6",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775486456
  },
  {
    "src_id": "Xét tuyển thẳng",
    "tgt_id": "Đơn vị đào tạo",
    "description": "Đơn vị đào tạo tổ chức xét tuyển thẳng cho những thí sinh đủ điều kiện.",
    "keywords": "triển khai,tổ chức",
    "weight": 1.0,
    "source_id": "chunk-4b93cbd5d0914f2cef5a210a16b4bbf5",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775486331
  },
  {
    "src_id": "hình thức trực tuyến hoặc trực tiếp",
    "tgt_id": "đăng ký dự tuyển",
    "description": "Đăng ký dự tuyển được thực hiện bằng hình thức trực tuyến hoặc trực tiếp tại đơn vị đào tạo.",
    "keywords": "hình thức,kênh thực hiện",
    "weight": 1.0,
    "source_id": "chunk-4b93cbd5d0914f2cef5a210a16b4bbf5",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775486331
  },
  {
    "src_id": "Đơn vị đào tạo",
    "tgt_id": "Đề án Tuyển sinh",
    "description": "Đơn vị đào tạo thông báo tuyển sinh kèm theo công bố đề án tuyển sinh.",
    "keywords": "công bố,thông báo kèm theo",
    "weight": 1.0,
    "source_id": "chunk-73e274f4a5ed1f38ed08014e717a6f92",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485520
  },
  {
    "src_id": "Quy trình đăng ký dự tuyển",
    "tgt_id": "Thí sinh",
    "description": "Quy trình đăng ký dự tuyển hướng đến thí sinh và cung cấp các thông tin cần thiết khác.",
    "keywords": "hướng dẫn thực hiện,thông tin cần thiết",
    "weight": 1.0,
    "source_id": "chunk-0d6008bd889a0ebc91d42d3a06f83f83",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485496
  },
  {
    "src_id": "n",
    "tgt_id": "Đơn vị đào tạo",
    "description": "n là mã số quy ước thống nhất được dùng trong đơn vị đào tạo.",
    "keywords": "phạm vi sử dụng,định danh",
    "weight": 1.0,
    "source_id": "chunk-18679ecca078f74da86923a647f33b04",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485756
  },
  {
    "src_id": "Chuyên viên Ban Đào tạo",
    "tgt_id": "Thư ký",
    "description": "Chuyên viên Ban Đào tạo đảm nhiệm vai trò Thư ký của Ban Chỉ đạo tuyển sinh.",
    "keywords": "vai trò,đảm nhiệm",
    "weight": 1.0,
    "source_id": "chunk-dccd9d905892f60251e114b78ae49b4c",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485033
  },
  {
    "src_id": "Danh sách thí sinh đủ điều kiện trúng tuyển",
    "tgt_id": "Đơn vị đào tạo",
    "description": "Đơn vị đào tạo công bố và tải danh sách thí sinh đủ điều kiện trúng tuyển lên hệ thống để xử lý nguyện vọng.",
    "keywords": "công bố và tải dữ liệu",
    "weight": 1.0,
    "source_id": "chunk-d70df8c903fddbcbfa9aedc2b549731f",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775486730
  },
  {
    "src_id": "Thông tin cá nhân",
    "tgt_id": "Trách nhiệm của thí sinh",
    "description": "Thí sinh phải cung cấp đầy đủ và bảo đảm tính chính xác thông tin cá nhân trong đăng ký dự tuyển.",
    "keywords": "cung cấp thông tin,tính chính xác",
    "weight": 1.0,
    "source_id": "chunk-bf836ea6db4d8badfb97990a59aa4543",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485483
  },
  {
    "src_id": "Đăng ký dự tuyển",
    "tgt_id": "Đơn vị đào tạo",
    "description": "Đơn vị đào tạo tạo điều kiện để thí sinh có nguyện vọng được đăng ký dự tuyển.",
    "keywords": "hỗ trợ quy trình",
    "weight": 1.0,
    "source_id": "chunk-c214b57125a6e684d66bb9c16816dffa",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485391
  },
  {
    "src_id": "Thông tin khu vực",
    "tgt_id": "Trách nhiệm của thí sinh",
    "description": "Thí sinh phải cung cấp đầy đủ và bảo đảm tính chính xác thông tin khu vực trong đăng ký dự tuyển.",
    "keywords": "cung cấp thông tin,tính chính xác",
    "weight": 1.0,
    "source_id": "chunk-bf836ea6db4d8badfb97990a59aa4543",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485484
  },
  {
    "src_id": "Điều 13. Tổ chức đăng ký và xét tuyển thẳng",
    "tgt_id": "Đơn vị đào tạo",
    "description": "Điều 13 quy định đơn vị đào tạo tổ chức đăng ký và tổ chức xét tuyển thẳng cho thí sinh thuộc đối tượng.",
    "keywords": "thực hiện,tổ chức",
    "weight": 1.0,
    "source_id": "chunk-4b93cbd5d0914f2cef5a210a16b4bbf5",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775486337
  },
  {
    "src_id": "Kiểm tra Thông tin và Hồ sơ Minh chứng",
    "tgt_id": "Đơn vị Đào tạo",
    "description": "Đơn vị đào tạo phải kiểm tra thông tin và hồ sơ minh chứng khi thí sinh nhập học.",
    "keywords": "kiểm soát điều kiện,thẩm định",
    "weight": 1.0,
    "source_id": "chunk-1cb8513b18d53e7800fe51928b1efe1c",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485497
  },
  {
    "src_id": "Trang Thông tin Điện tử của Đơn vị",
    "tgt_id": "Đơn vị đào tạo",
    "description": "Đơn vị đào tạo công bố thông tin tuyển sinh trên trang thông tin điện tử của đơn vị.",
    "keywords": "kênh công bố,đăng tải",
    "weight": 1.0,
    "source_id": "chunk-73e274f4a5ed1f38ed08014e717a6f92",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "created_at": 1775485522
  }
]
```

## Chunks

```json
[
  {
    "reference_id": "1",
    "content": "h theo các quy định của nhà nước;\n    c.  Cung cấp đầy đủ thông tin, tư vấn và hướng dẫn thí sinh, không để thí sinh đăng ký dự tuyển vào một nhóm ngành/ngành, chương trình đào tạo hay theo một phương thức tuyển sinh của đơn vị đào tạo mà không đủ điều kiện;\n    d.  Bảo đảm quy trình xét tuyển chính xác, công bằng, khách quan; thực hiện các cam kết theo đề án tuyển sinh đã công bố;\n    đ. Kiểm tra thông tin và hồ sơ minh chứng khi thí sinh nhập học, bảo đảm tất cả thí sinh nhập học phải đủ điều kiện trúng tuyển;\n    e.  Giải quyết đơn thư phản ánh, khiếu nại, tố cáo liên quan tới công tác xét tuyển của đơn vị đào tạo theo quy định của pháp luật.",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "chunk_id": "chunk-1cb8513b18d53e7800fe51928b1efe1c"
  },
  {
    "reference_id": "1",
    "content": "áo xét tuyển đợt bổ sung (nếu có);\n    h. Báo cáo tổng kết công tác tuyển sinh của đơn vị trước ngày 31/10;\n\n2.  Chế độ lưu trữ\n\nĐơn vị đào tạo có trách nhiệm lưu trữ, bảo quản an toàn các tài liệu liên quan tới công tác tuyển sinh theo các quy định do Bộ GD&ĐT ban hành.\n\n    a.  Quyết định trúng tuyển, quyết định công nhận sinh viên là tài liệu lưu trữ được bảo quản vĩnh viễn tại đơn vị đào tạo;\n    b.  Tài liệu khác liên quan đến tuyển sinh, đào tạo được lưu trữ, bảo quản trong suốt quá trình đào tạo;\n    c.  Việc tiêu hủy tài liệu liên quan tuyển sinh, đào tạo hết thời gian lưu trữ được thực hiện theo quy định hiện hành của nhà nước.",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "chunk_id": "chunk-99f0cf87ddf1406829eba421dbb9a9cc"
  },
  {
    "reference_id": "1",
    "content": "yển sinh và cam kết trách nhiệm của đơn vị đào tạo.\n\n3.  Đơn vị đào tạo thông báo tuyển sinh kèm theo công bố đề án tuyển sinh trên trang thông tin điện tử của đơn vị, cổng thông tin tuyển sinh của ĐHQGHN và qua các hình thức phù hợp khác trước khi mở đăng ký dự tuyển của đợt tuyển sinh đầu tiên ít nhất 30 ngày; trường hợp điều chỉnh, bổ sung (nếu có) trước ít nhất 15 ngày.",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "chunk_id": "chunk-73e274f4a5ed1f38ed08014e717a6f92"
  },
  {
    "reference_id": "1",
    "content": "van_ban | quyet_dinh_1328_quy_che_tuyen_sinh_vnu | 2023-04-18\n\n## Điều 24. Chế độ báo cáo và lưu trữ\n\n1.  Chế độ báo cáo \nHằng năm, HĐTS các đơn vị gửi báo cáo Ban Chỉ đạo tuyển sinh (qua Ban Đào tạo):\n    a.  Quyết định thành lập HĐTS và các tiểu ban chuyên môn;\n    b.  Đề án tuyển sinh (theo mẫu tại Phụ lục V Quy chế này) trước khi công bố ít nhất 10 ngày;\n    c.  Quy định, quy trình (nếu có) và các văn bản hướng dẫn tuyển sinh của đơn vị đào tạo;\n    d.  Kết quả lọc ảo trước khi nhập kết quả xét tuyển lên hệ thống lọc ảo (lần cuối); điểm trúng tuyển theo nhóm ngành/ngành, chương trình đào tạo trước khi công bố kết quả trúng tuyển;\n    đ. Danh sách thí sinh trúng tuyển (dự kiến) theo các phương thức tuyển sinh trước khi ra quyết định công nhận trúng tuyển chính thức;\n    e.  Quyết định trúng tuyển và danh sách thí sinh trúng tuyển theo các phương thức tuyển sinh; Danh sách nhập học theo các phương thức tuyển sinh;\n    g.  Đối với các ngành chưa tuyển đủ chỉ tiêu trong đợt 1, đơn vị báo cáo Ban Chỉ đạo tuyển sinh xem xét, phê duyệt kế hoạch xét tuyển đợt bổ sung trước khi ra thông báo xét tuyển đợt bổ sung (nếu có);\n    h. Báo cáo tổng kết công tác tuyển sinh của đơn vị trước ngày",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "chunk_id": "chunk-5ef7502b5fff13cfaf706ccf8f094af6"
  },
  {
    "reference_id": "1",
    "content": "định việc tiếp nhận thí sinh vào học hoặc bảo lưu kết quả tuyển sinh để thí sinh vào học sau.\n4.  Thí sinh đã xác nhận nhập học tại một đơn vị đào tạo không được tham gia xét tuyển ở nơi khác hoặc ở các đợt xét tuyển bổ sung, trừ trường hợp được đơn vị đào tạo cho phép.\n5.  Ký và đóng dấu giấy báo thí sinh trúng tuyển\n- Hiệu trưởng các trường đại học thành viên ký và đóng dấu giấy báo thí sinh trúng tuyển vào trường.\n- Trưởng Ban Đào tạo ký và đóng dấu giấy báo thí sinh trúng tuyển vào các trường/khoa trực thuộc.",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "chunk_id": "chunk-1f39a0ff78c35fa4b16ff781cf5edaf3"
  },
  {
    "reference_id": "1",
    "content": "m các môn học xét tuyển tương đương với yêu cầu xét tuyển thí sinh có chứng chỉ A-Level Quy định tại Quy chế này)_ kết hợp với kiểm tra kiến thức chuyên môn và năng lực Tiếng Việt hoặc năng lực ngoại ngữ _(tùy theo yêu cầu của ngành học để xét tuyển)_ đáp ứng quy định hiện hành của Bộ GD&ĐT và của ĐHQGHN.\n\n4.  Đơn vị đào tạo quy định hình thức ưu tiên xét tuyển khác đối với các trường hợp sau đây:\n\n    a.  Thí sinh quy định tại khoản 1, 2 Điều này dự tuyển vào các ngành theo nguyện vọng (không dùng quyền ưu tiên tuyển thẳng);\n\n    b.  Thí sinh đoạt giải khuyến khích trong kỳ thi chọn học sinh giỏi quốc gia; thí sinh đoạt giải tư trong cuộc thi khoa học, kỹ thuật cấp quốc gia dự tuyển vào ngành phù hợp với môn thi hoặc nội dung đề tài dự thi đã đoạt giải; thời gian đoạt giải không quá 3 năm tính tới thời điểm xét tuyển;\n    \n    c.  Thí sinh đoạt huy chương vàng, bạc, đồng các giải thể dục thể thao cấp quốc gia tổ chức một lần trong năm và thí sinh được Tổng cục Thể dục thể thao có quyết định công nhận là kiện tướng quốc gia dự tuyển vào các ngành thể dục thể thao phù hợp; thời gian đoạt giải không quá 4 năm tính tới thời điểm xét tuyển;\n\n    d.  Thí sinh đoạt giải chính thức trong",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "chunk_id": "chunk-d830f682b07ebeb668d54551a6209b96"
  },
  {
    "reference_id": "1",
    "content": "van_ban | quyet_dinh_1328_quy_che_tuyen_sinh_vnu | 2023-04-18\n\n## Điều 19. Trách nhiệm của các bên liên quan trong công tác xét tuyển\n\n1.  Trách nhiệm của thí sinh\n    a.  Tìm hiểu kỹ thông tin tuyển sinh của các đơn vị đào tạo, không đăng ký nguyện vọng vào những ngành, chương trình đào tạo hay phương thức tuyển sinh mà không đủ điều kiện;\n    b.  Cung cấp đầy đủ và bảo đảm tính chính xác của tất cả thông tin đăng ký dự tuyển, bao gồm cả thông tin cá nhân, thông tin khu vực và đối tượng ưu tiên (nếu có), nguyện vọng đăng ký; tính xác thực của các giấy tờ minh chứng;\n    c.  Đồng ý để đơn vị đào tạo mà mình dự tuyển được quyền sử dụng thông tin, dữ liệu cần thiết phục vụ cho công tác xét tuyển;\n    d.  Hoàn thành thanh toán lệ phí tuyển sinh trước khi kết thúc thủ tục đăng ký dự tuyển.\n\n2.  Trách nhiệm của đơn vị đào tạo\n    a.  Cung cấp đầy đủ, đúng định dạng và bảo đảm tính xác thực của thông tin, dữ liệu tuyển sinh lên hệ thống theo hướng dẫn của Bộ GD&ĐT;\n    b.  Quy định (hoặc thống nhất với các đơn vị đào tạo khác) về mức thu, phương thức thu và sử dụng lệ phí dịch vụ tuyển sinh theo các quy định của nhà nước;\n    c.  Cung cấp đầy đủ thông tin, tư vấn và hướng dẫn thí sinh, k",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "chunk_id": "chunk-bf836ea6db4d8badfb97990a59aa4543"
  },
  {
    "reference_id": "1",
    "content": "van_ban | quyet_dinh_1328_quy_che_tuyen_sinh_vnu | 2023-04-18\n\n## Chương I QUY ĐỊNH CHUNG\n\n**Điều 1. Phạm vi điều chỉnh và đối tượng áp dụng**\n\n1.  Quy chế này quy định những nguyên tắc, yêu cầu, tiêu chuẩn, quy trình, quy định cụ thể về xét tuyển, quyền hạn và trách nhiệm của các bên liên quan trong công tác tuyển sinh đại học chính quy tại Đại học Quốc gia Hà Nội (ĐHQGHN);\n2.  Quy chế này áp dụng đối với các đơn vị, tổ chức, cá nhân có liên quan trong công tác tuyển sinh đại học chính quy vào các chương trình đào tạo do Giám đốc ĐHQGHN, Hiệu trưởng các trường thành viên cấp bằng và các chương trình đào tạo liên kết với cơ sở giáo dục nước ngoài do ĐHQGHN cấp bằng, hai bên cùng cấp bằng (_không áp dụng đối với tuyển sinh các chương trình đào tạo liên kết do các cơ sở giáo dục nước ngoài cấp bằng)_.\n\n## Điều 2. Giải thích từ ngữ\n\nTrong văn bản này, các từ ngữ dưới đây được hiểu như sau:\n\n1.  Phạm vi tuyển sinh là các chương trình, ngành, nhóm ngành và lĩnh vực được tổ chức tuyển sinh trong một đợt hoặc theo một phương thức tuyển sinh nhất định.\n2.  Đơn vị đào tạo là trường đại học thành viên, trường/khoa trực thuộc ĐHQGHN có chức năng nhiệm vụ tổ chức đào tạo đại học.\n3.  Dự tuyển",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "chunk_id": "chunk-39701be07619a29470685a24ef242d87"
  },
  {
    "reference_id": "1",
    "content": "ệp (trên tổng số nhập học) và tỉ lệ có việc làm phù hợp trình độ chuyên môn của sinh viên tốt nghiệp theo Phụ lục V của Quy chế này;\n\n    b.  Thông tin đầy đủ về chi phí đào tạo, mức thu học phí, mức thu dịch vụ tuyển sinh và khoản thu dịch vụ khác cho lộ trình cả khóa học, từng năm học; chính sách học bổng, miễn giảm học phí, hỗ trợ tài chính, chỗ ở ký túc xá và các chính sách ưu đãi, hỗ trợ khác dành cho người học;\n    \n    c.  Kế hoạch tuyển sinh và phạm vi tuyển sinh các đợt trong năm (trong đó đợt 1 tuyển sinh phải phù hợp với kế hoạch chung do Bộ GD&ĐT ban hành), gồm cả quy định về đối tượng và điều kiện tuyển sinh, phương thức tuyển sinh, tổ hợp xét tuyển và chỉ tiêu tuyển sinh đối với các ngành, chương trình đào tạo; quy trình, thủ tục đăng ký dự tuyển và các thông tin cần thiết khác cho thí sinh; Riêng các chương trình đào tạo tài năng, chất lượng cao phải có quy định về điều kiện về ngoại ngữ; các chương trình đào tạo thí điểm phải ghi chú cụ thể, rõ ràng, đầy đủ thông tin để không gây hiểu lầm cho thí sinh.\n    \n    d.  Các phương án xử lý rủi ro khi triển khai công tác tuyển sinh và cam kết trách nhiệm của đơn vị đào tạo.\n\n3.  Đơn vị đào tạo thông báo tuyển sinh kèm the",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "chunk_id": "chunk-0d6008bd889a0ebc91d42d3a06f83f83"
  },
  {
    "reference_id": "1",
    "content": "van_ban | quyet_dinh_1328_quy_che_tuyen_sinh_vnu | 2023-04-18\n\n**Chương III**\n\n# TỔ CHỨC THỰC HIỆN\n\n## Điều 20. Tổ chức, nhiệm vụ và quyền hạn của ĐHQGHN\n\n1.  Ban hành kế hoạch tuyển sinh chung và xây dựng các văn bản hướng dẫn về công tác tuyển sinh tại ĐHQGHN;\n2.  Giám đốc ĐHQGHN ra quyết định thành lập Ban Chỉ đạo tuyển sinh của ĐHQGHN để chỉ đạo các đơn vị thuộc ĐHQGHN trong công tác tuyển sinh đảm bảo đúng quy định của Quy chế này.\n    2.1.  Thành phần Ban Chỉ đạo tuyển sinh gồm có:\n        a.  Trưởng ban: Đại diện Ban Giám đốc;\n        b.  Phó Trưởng ban: Trưởng ban Đào tạo;\n        c.  Các uỷ viên: Đại diện lãnh đạo Ban Đào tạo, Ban Thanh tra và Pháp chế, Văn phòng ĐHQGHN; đại diện lãnh đạo các đơn vị đào tạo, Giám đốc Trung tâm Khảo thí ĐHQGHN;\n        d.  Thư ký: Chuyên viên Ban Đào tạo.\n\n        _Những người có người thân (con, vợ/chồng, anh, chị, em ruột của mình và của chồng/vợ) dự thi hay đăng ký xét tuyển vào ĐHQGHN không được tham gia Ban Chỉ đạo tuyển sinh._\n\n    2.2.  Nhiệm vụ và quyền hạn của Ban Chỉ đạo tuyển sinh\n\n        a.  Chỉ đạo và tổ chức các hoạt động truyền thông, tư vấn tuyển sinh của ĐHQGHN;\n        b.  Chỉ đạo và tổ chức triển khai công tác tuyển sinh",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "chunk_id": "chunk-dccd9d905892f60251e114b78ae49b4c"
  },
  {
    "reference_id": "1",
    "content": "hợp rủi ro.\n\n2.  Bình đẳng giữa các đơn vị đào tạo\n    a.  Về hợp tác: Hợp tác bình đẳng nhằm nâng cao chất lượng và hiệu quả tuyển sinh, đồng thời mang lại lợi ích tốt nhất cho thí sinh;\n    b.  Về cạnh tranh: Cạnh tranh trung thực, công bằng và lành mạnh trong tuyển sinh theo quy định của pháp luật về cạnh tranh.\n3.  Minh bạch đối với xã hội\n    a.  Về minh bạch thông tin: Đơn vị đào tạo có trách nhiệm công bố thông tin tuyển sinh đầy đủ, rõ ràng và kịp thời qua các phương tiện truyền thông phù hợp để xã hội, cơ quan quản lý nhà nước và ĐHQGHN cùng giám sát;\n    b.  Về trách nhiệm giải trình: Đơn vị đào tạo có trách nhiệm báo cáo theo yêu cầu của ĐHQGHN, các cơ quan quản lý nhà nước và giải trình với xã hội về những vấn đề lớn, gây bức xúc cho người dân.",
    "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
    "chunk_id": "chunk-6bfc5f2ad22b00d8a493668fdba2fd14"
  },
  {
    "reference_id": "2",
    "content": "https://uet.vnu.edu.vn/cac-chung-chi-ngoai-ngu-dap-ung-dieu-kien-chuan-dau-ra/\n\nCác chứng chỉ ngoại ngữ đáp ứng điều kiện chuẩn đầu ra Căn cứ Quy chế đào tạo đại học ban hành theo Quyết định số 5115/QĐ-ĐHQGHN ngày 25/12/2014 của Giám đốc Đại học Quốc gia Hà Nội; Căn cứ Công văn số 70/ĐHQGHN-ĐT ngày 12/01/2021 về việc “Danh sách các cơ sở cấp chứng chỉ Ngoại ngữ (tiếng Anh) theo Khung năng lực ngoại ngữ 6 bậc dùng cho Việt Nam” của Đại học Quốc gia Hà Nội; Phòng Đào tạo (P.ĐT) trân trọng gửi đến các đơn vị trong trường và sinh viên đại học hệ chính quy thông tin về các chứng chỉ Ngoại ngữ (tiếng Anh) đáp ứng điều kiện về chuẩn đầu ra như sau: 1. Bảng tham chiếu mức điểm tối thiểu một số chứng chỉ Tiếng Anh tương đương bậc 3 và bậc 4 theo Khung năng lực Ngoại ngữ 6 bậc dùng cho Việt Nam Khung năng lực ngoại ngữ VN IELTS TOEFL TOEIC (4 kỹ năng) Cambridge Tests Vietnamese Standardized Test of English Proficiency Bậc 3 4.5 460 ITP 42 iBT Reading 275 Listening 275 Speaking 120 Writing 120 KET (Distinction 140) PET (Pass 140) FCE (Level B1-140) VSTEP.3-5 (4.0) Bậc 4 5.5 543 ITP 72 iBT Reading 385 Listening 400 Speaking 160 Writing 150 KET (Distinction 160) PET (Pass 160) FCE (Level B1-160",
    "file_path": "..\\..\\data\\data_1000_chunk_512.json",
    "chunk_id": "chunk-1a3df01c18894f70ba1089c4742063c5"
  }
]
```

## References

```json
[]
```

## Raw LLM Response

```json
{
  "status": "success",
  "message": "Query processed successfully",
  "data": {
    "entities": [
      {
        "entity_name": "Các đơn vị đào tạo",
        "entity_type": "đơn_vị_trực_thuộc",
        "description": "Các đơn vị đào tạo được đề cập như chủ thể tuyển sinh, nơi thí sinh tìm hiểu thông tin tuyển sinh.",
        "source_id": "chunk-bf836ea6db4d8badfb97990a59aa4543",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485431
      },
      {
        "entity_name": "Thông tin, Tư vấn và Hướng dẫn Thí sinh",
        "entity_type": "method",
        "description": "Nội dung cung cấp đầy đủ thông tin, tư vấn và hướng dẫn thí sinh để thí sinh không đăng ký dự tuyển khi chưa đủ điều kiện.",
        "source_id": "chunk-1cb8513b18d53e7800fe51928b1efe1c",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485439
      },
      {
        "entity_name": "đơn vị đào tạo",
        "entity_type": "đơn_vị_trực_thuộc",
        "description": "đơn vị đào tạo là chủ thể phối hợp triển khai các quy trình đăng ký, tổ chức xét tuyển, xử lý nguyện vọng và xác nhận nhập học.<SEP>đơn vị đào tạo là chủ thể có thể quy định cụ thể về đối tượng, điều kiện dự tuyển cho mỗi phương thức tuyển sinh.",
        "source_id": "chunk-42c0bd7eac70305a81f43b3e9300d670<SEP>chunk-c0d3f2c39bc7c8e37aab19434ceb8862",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485329
      },
      {
        "entity_name": "Đơn vị Đào tạo",
        "entity_type": "đơn_vị_trực_thuộc",
        "description": "Đơn vị đào tạo tải lên hệ thống danh sách thí sinh dự kiến đủ điều kiện trúng tuyển, lặp lại quy trình xét tuyển ở chu kỳ sau và quyết định điểm trúng tuyển ở chu kỳ cuối.<SEP>Đơn vị đào tạo được nêu như chủ thể thực hiện các nghĩa vụ trong công tác xét tuyển theo đề án tuyển sinh đã công bố và theo quy định pháp luật.<SEP>Đơn vị đào tạo thực hiện công bố kế hoạch xét tuyển, hướng dẫn đăng ký, công bố điểm trúng tuyển và điều kiện, tiêu chí phụ (nếu có), cũng như tổ chức cho thí sinh tra cứu kết quả.<SEP>Tổ chức thực hiện xác nhận nhập học và có thể cho phép thí sinh tham gia xét tuyển ở nơi khác hoặc ở đợt bổ sung.",
        "source_id": "chunk-ca3d17d3c1f7fff2b4d41619bb94314f<SEP>chunk-1cb8513b18d53e7800fe51928b1efe1c<SEP>chunk-cf425f7ca685593f88901f2f6d924893<SEP>chunk-1f39a0ff78c35fa4b16ff781cf5edaf3",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485931
      },
      {
        "entity_name": "Minh Bạch Thông Tin",
        "entity_type": "concept",
        "description": "Đơn vị đào tạo có trách nhiệm công bố thông tin tuyển sinh đầy đủ, rõ ràng và kịp thời qua các phương tiện truyền thông phù hợp để xã hội, cơ quan quản lý nhà nước và ĐHQGHN cùng giám sát.",
        "source_id": "chunk-6bfc5f2ad22b00d8a493668fdba2fd14",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775486113
      },
      {
        "entity_name": "đăng ký dự tuyển",
        "entity_type": "method",
        "description": "Hoạt động đăng ký dự tuyển của thí sinh thuộc đối tượng xét tuyển thẳng, thực hiện trực tuyến hoặc trực tiếp tại đơn vị đào tạo.",
        "source_id": "chunk-4b93cbd5d0914f2cef5a210a16b4bbf5",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775486301
      },
      {
        "entity_name": "Đơn Vị Đào Tạo",
        "entity_type": "đơn_vị_trực_thuộc",
        "description": "Đơn Vị Đào Tạo tổ chức xét tuyển theo các phương thức và tiêu chí riêng hoặc phối hợp theo nhóm để tổ chức xét tuyển theo phương thức và tiêu chí chung.<SEP>Đơn vị đào tạo là lựa chọn về nơi học tập, được thể hiện kèm mã trường trong phần lựa chọn đơn vị đào tạo.<SEP>Đơn vị đào tạo là nơi có dữ liệu trúng tuyển và nhập học được hệ thống hỗ trợ tuyển sinh chung quản lý.<SEP>Đơn vị đào tạo được nêu là chủ thể căn cứ kết quả học tập THPT và yêu cầu ngành đào tạo để quyết định nhận thí sinh vào học.<SEP>Đơn vị đào tạo tham gia tuyển sinh và có các trách nhiệm như hợp tác bình đẳng, cạnh tranh lành mạnh, công bố thông tin tuyển sinh minh bạch và báo cáo/giải trình theo yêu cầu của ĐHQGHN và cơ quan quản lý nhà nước.",
        "source_id": "chunk-1b5dfa8d570d9f115a0abdcc7e2ecb66<SEP>chunk-81d92fffe062e7c8fcbd0316fa088c66<SEP>chunk-170b153fd5ea4a9ddacf6c3b10783810<SEP>chunk-e2e77743fb90d76576cdd797d7c3d1da<SEP>chunk-6bfc5f2ad22b00d8a493668fdba2fd14",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775486117
      },
      {
        "entity_name": "các đơn vị đào tạo",
        "entity_type": "đơn_vị_trực_thuộc",
        "description": "các đơn vị đào tạo có đại diện tham gia thành phần Ban Chỉ đạo tuyển sinh.<SEP>các đơn vị đào tạo thực hiện quyền tự chủ, trách nhiệm giải trình và các biện pháp bảo đảm điều kiện tuyển sinh.",
        "source_id": "chunk-dccd9d905892f60251e114b78ae49b4c<SEP>chunk-0abf0789ba93e1147b98fac10073dd1f",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485842
      },
      {
        "entity_name": "Đơn vị đào tạo",
        "entity_type": "đơn_vị_trực_thuộc",
        "description": "Đơn vị đào tạo là chủ thể thực hiện các nội dung liên quan đến tuyển sinh và đào tạo theo quy định, bao gồm việc tổ chức thông báo tuyển sinh và công bố đề án tuyển sinh trước khi mở đăng ký dự tuyển. Trên cơ sở các nguyên tắc chung được nêu và công khai trong đề án tuyển sinh, đơn vị đào tạo thực hiện quy đổi theo các quy định cụ thể, triển khai các biện pháp cần thiết để phục vụ thí sinh. Trong quá trình tuyển sinh, Đơn vị đào tạo quyết định danh sách thí sinh trúng tuyển theo từng nhóm ngành/ngành và theo từng chương trình đào tạo, công bố điểm trúng tuyển; nếu có quy định thì đồng thời công bố các điều kiện/tiêu chí phụ kèm theo, các hình thức ưu tiên xét tuyển cho từng trường hợp và xác định nhóm ngành/ngành hoặc chương trình mà các đối tượng tuyển thẳng được vào theo quy định. Cuối cùng, đơn vị đào tạo chịu trách nhiệm tổ chức triển khai toàn bộ công tác tuyển sinh đúng với nội dung trong thông báo tuyển sinh và đề án tuyển sinh.\n\nĐơn vị đào tạo có thể gắn với các trường đại học thành viên và các trường/khoa trực thuộc ĐHQGHN (những đơn vị có chức năng, nhiệm vụ tổ chức đào tạo đại học). Đơn vị đào tạo sử dụng mã số quy ước thống nhất để định danh nhóm ngành/ngành hoặc chương trình đào tạo và áp dụng phương thức tuyển sinh. Ở giai đoạn hậu tuyển, Đơn vị đào tạo gửi giấy báo trúng tuyển, hướng dẫn thủ tục nhập học và xem xét tiếp nhận hoặc bảo lưu kết quả tuyển sinh khi thí sinh không xác nhận nhập học; đồng thời phải giải trình về căn cứ khoa học và thực tiễn trong việc xác định phương thức tuyển sinh, phương thức xét tuyển, tổ hợp xét tuyển và phân bổ chỉ tiêu tuyển sinh. Đơn vị đào tạo cũng thực hiện cam kết, tư vấn, hỗ trợ và giải quyết khiếu nại để bảo vệ quyền lợi của thí sinh, đặc biệt tổ chức cho thí sinh thuộc đối tượng xét tuyển thẳng đăng ký dự tuyển và tổ chức xét tuyển thẳng cho các thí sinh đủ điều kiện; có kế hoạch và thông báo xét tuyển sớm, tổ chức xét tuyển cho thí sinh đã hoàn thành thủ tục dự tuyển, và công bố/tải danh sách thí sinh đủ điều kiện trúng tuyển lên hệ thống.\n\nVề tổ chức, Đơn vị đào tạo là nơi có Thủ trưởng thành lập HĐTS và chịu trách nhiệm tổ chức, điều hành toàn bộ công tác tuyển sinh theo quy định. Nếu Đơn vị đào tạo vi phạm về công tác tuyển sinh thì sẽ bị áp dụng xử lý theo quy định của ĐHQGHN và các quy định pháp luật hiện hành.",
        "source_id": "chunk-ddace097418fed36cbe37da8f4249576<SEP>chunk-3f8b3d332cf0c347e8de3d57dc270374<SEP>chunk-c214b57125a6e684d66bb9c16816dffa<SEP>chunk-0d6008bd889a0ebc91d42d3a06f83f83<SEP>chunk-ffb1cfd0c23e7fa4206abe42c582cc74<SEP>chunk-73e274f4a5ed1f38ed08014e717a6f92<SEP>chunk-d830f682b07ebeb668d54551a6209b96<SEP>chunk-ff59c46f3ab103315ca32379f39a3d18<SEP>chunk-18679ecca078f74da86923a647f33b04<SEP>chunk-39701be07619a29470685a24ef242d87<SEP>chunk-d847432d893deb66ba9545e43db1c0ff<SEP>chunk-c482f693ef8c5985db5d7021905a1633<SEP>chunk-34684aec0d79f3237acdda225af3e906<SEP>chunk-4b93cbd5d0914f2cef5a210a16b4bbf5<SEP>chunk-759233ad94ecba2518607c2566ed9fbe<SEP>chunk-d70df8c903fddbcbfa9aedc2b549731f<SEP>chunk-04f0fde7624010888d30f43632b7cf85",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775486854
      },
      {
        "entity_name": "Đơn vị đào tạo thông báo tuyển sinh",
        "entity_type": "event",
        "description": "Hành vi thông báo tuyển sinh của đơn vị đào tạo, đi kèm việc công bố đề án tuyển sinh trước khi mở đăng ký dự tuyển của đợt tuyển sinh đầu tiên.",
        "source_id": "chunk-73e274f4a5ed1f38ed08014e717a6f92",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485471
      }
    ],
    "relationships": [
      {
        "src_id": "ĐHQGHN",
        "tgt_id": "Đơn vị đào tạo",
        "description": "Đơn vị đào tạo báo cáo ĐHQGHN kết quả xét tuyển thẳng trước khi công bố kết quả theo kế hoạch chung.<SEP>Đơn vị đào tạo vi phạm về tuyển sinh bị áp dụng xử lý theo quy định của ĐHQGHN.",
        "keywords": "báo cáo,căn cứ xử lý,phê duyệt theo kế hoạch,quy định",
        "weight": 2.0,
        "source_id": "chunk-4b93cbd5d0914f2cef5a210a16b4bbf5<SEP>chunk-759233ad94ecba2518607c2566ed9fbe",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775486501
      },
      {
        "src_id": "Thông tin, Tư vấn và Hướng dẫn Thí sinh",
        "tgt_id": "Đơn vị Đào tạo",
        "description": "Đơn vị đào tạo phải cung cấp đầy đủ thông tin, tư vấn và hướng dẫn thí sinh để tránh việc đăng ký dự tuyển khi không đủ điều kiện.",
        "keywords": "trách nhiệm hỗ trợ,điều kiện đăng ký",
        "weight": 1.0,
        "source_id": "chunk-1cb8513b18d53e7800fe51928b1efe1c",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485493
      },
      {
        "src_id": "Minh Bạch Thông Tin",
        "tgt_id": "ĐHQGHN",
        "description": "Minh bạch thông tin tuyển sinh được thực hiện để ĐHQGHN cùng giám sát.",
        "keywords": "giám sát,thông tin tuyển sinh",
        "weight": 1.0,
        "source_id": "chunk-6bfc5f2ad22b00d8a493668fdba2fd14",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775486196
      },
      {
        "src_id": "Minh Bạch Thông Tin",
        "tgt_id": "Đơn Vị Đào Tạo",
        "description": "Đơn vị đào tạo có trách nhiệm công bố thông tin tuyển sinh đầy đủ, rõ ràng và kịp thời để xã hội, cơ quan quản lý nhà nước và ĐHQGHN cùng giám sát.",
        "keywords": "công bố thông tin,giám sát",
        "weight": 1.0,
        "source_id": "chunk-6bfc5f2ad22b00d8a493668fdba2fd14",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775486188
      },
      {
        "src_id": "Thí sinh",
        "tgt_id": "Đơn vị đào tạo",
        "description": "Đơn vị đào tạo tổ chức xét tuyển cho những thí sinh đã hoàn thành thủ tục dự tuyển.",
        "keywords": "tổ chức xét tuyển",
        "weight": 1.0,
        "source_id": "chunk-d70df8c903fddbcbfa9aedc2b549731f",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775486721
      },
      {
        "src_id": "Đơn vị đào tạo",
        "tgt_id": "Đơn vị đào tạo thông báo tuyển sinh",
        "description": "Đơn vị đào tạo thực hiện việc thông báo tuyển sinh theo yêu cầu của quy định.",
        "keywords": "hành động,trách nhiệm",
        "weight": 1.0,
        "source_id": "chunk-73e274f4a5ed1f38ed08014e717a6f92",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485533
      },
      {
        "src_id": "Đơn vị đào tạo",
        "tgt_id": "Đề án tuyển sinh",
        "description": "Đơn vị đào tạo công bố công khai nguyên tắc quy đổi cụ thể trong Đề án tuyển sinh.<SEP>Đơn vị đào tạo xây dựng, công bố và thực hiện đề án tuyển sinh.",
        "keywords": "công bố,trách nhiệm,văn bản công khai,xây dựng và thực hiện",
        "weight": 2.0,
        "source_id": "chunk-ddace097418fed36cbe37da8f4249576<SEP>chunk-ffb1cfd0c23e7fa4206abe42c582cc74",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485511
      },
      {
        "src_id": "Bộ GD&ĐT",
        "tgt_id": "Trách nhiệm của đơn vị đào tạo",
        "description": "Đơn vị đào tạo phải thực hiện việc cung cấp thông tin/dữ liệu tuyển sinh lên hệ thống theo hướng dẫn của Bộ GD&ĐT.",
        "keywords": "quy trình dữ liệu,tuân thủ hướng dẫn",
        "weight": 1.0,
        "source_id": "chunk-bf836ea6db4d8badfb97990a59aa4543",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485485
      },
      {
        "src_id": "HĐTS",
        "tgt_id": "Đơn vị đào tạo",
        "description": "Đơn vị đào tạo có HĐTS được thành lập để tổ chức và điều hành công tác tuyển sinh.",
        "keywords": "cấu phần tuyển sinh,quản lý",
        "weight": 1.0,
        "source_id": "chunk-04f0fde7624010888d30f43632b7cf85",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775486982
      },
      {
        "src_id": "Các đơn vị đào tạo",
        "tgt_id": "Trách nhiệm của thí sinh",
        "description": "Thí sinh phải tìm hiểu thông tin tuyển sinh do các đơn vị đào tạo công bố.",
        "keywords": "tìm hiểu thông tin,đối tượng tuyển sinh",
        "weight": 1.0,
        "source_id": "chunk-bf836ea6db4d8badfb97990a59aa4543",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485474
      },
      {
        "src_id": "Chương trình đào tạo",
        "tgt_id": "Ngôn ngữ đào tạo",
        "description": "Đề án tuyển sinh nêu thông tin về ngôn ngữ đào tạo.",
        "keywords": "ngôn ngữ,thông tin liên quan",
        "weight": 1.0,
        "source_id": "chunk-ffb1cfd0c23e7fa4206abe42c582cc74",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485521
      },
      {
        "src_id": "Thông tin tuyển sinh",
        "tgt_id": "Trách nhiệm của thí sinh",
        "description": "Thí sinh có trách nhiệm tìm hiểu kỹ thông tin tuyển sinh của các đơn vị đào tạo và chỉ đăng ký nguyện vọng phù hợp điều kiện.",
        "keywords": "nghĩa vụ tìm hiểu,đăng ký đúng điều kiện",
        "weight": 1.0,
        "source_id": "chunk-bf836ea6db4d8badfb97990a59aa4543",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485469
      },
      {
        "src_id": "Bộ GD&ĐT",
        "tgt_id": "Đơn Vị",
        "description": "Đơn vị đào tạo thực hiện lưu trữ, bảo quản tài liệu theo các quy định do Bộ GD&ĐT ban hành.",
        "keywords": "trách nhiệm,tuân thủ quy định",
        "weight": 1.0,
        "source_id": "chunk-99f0cf87ddf1406829eba421dbb9a9cc",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775486481
      },
      {
        "src_id": "Giá trị thông tin, dữ liệu cần thiết",
        "tgt_id": "Trách nhiệm của thí sinh",
        "description": "Thí sinh đồng ý để đơn vị đào tạo sử dụng thông tin/dữ liệu cần thiết phục vụ công tác xét tuyển.",
        "keywords": "phục vụ xét tuyển,đồng ý sử dụng dữ liệu",
        "weight": 1.0,
        "source_id": "chunk-bf836ea6db4d8badfb97990a59aa4543",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485494
      },
      {
        "src_id": "Mức điểm ưu tiên",
        "tgt_id": "Đơn vị đào tạo",
        "description": "Đơn vị đào tạo quy đổi cụ thể mức điểm ưu tiên theo nguyên tắc chung và công bố công khai trong Đề án tuyển sinh.",
        "keywords": "công bố,quy đổi",
        "weight": 1.0,
        "source_id": "chunk-ddace097418fed36cbe37da8f4249576",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485085
      },
      {
        "src_id": "công tác tuyển sinh",
        "tgt_id": "Đơn vị đào tạo",
        "description": "Quy định nêu đơn vị đào tạo vi phạm về công tác tuyển sinh và chịu xử lý theo mức độ.",
        "keywords": "hoạt động,phạm vi vi phạm",
        "weight": 1.0,
        "source_id": "chunk-759233ad94ecba2518607c2566ed9fbe",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775486493
      },
      {
        "src_id": "Chuẩn bị điều kiện tham gia dự tuyển và thực hiện các bước theo kế hoạch tuyển sinh",
        "tgt_id": "Thí sinh",
        "description": "Thí sinh dùng thông tin từ đề án tuyển sinh để chuẩn bị điều kiện dự tuyển và thực hiện các bước theo kế hoạch tuyển sinh.",
        "keywords": "chuẩn bị,thực hiện kế hoạch",
        "weight": 1.0,
        "source_id": "chunk-ffb1cfd0c23e7fa4206abe42c582cc74",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485517
      },
      {
        "src_id": "Hệ thống",
        "tgt_id": "Trách nhiệm của đơn vị đào tạo",
        "description": "Đơn vị đào tạo phải cung cấp đầy đủ, đúng định dạng và bảo đảm tính xác thực thông tin, dữ liệu tuyển sinh lên hệ thống theo hướng dẫn.",
        "keywords": "cung cấp dữ liệu,tuân thủ định dạng",
        "weight": 1.0,
        "source_id": "chunk-bf836ea6db4d8badfb97990a59aa4543",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485483
      },
      {
        "src_id": "Đơn vị đào tạo",
        "tgt_id": "Ưu tiên xét tuyển",
        "description": "Đơn vị đào tạo quy định hình thức ưu tiên xét tuyển khác đối với các nhóm thí sinh được nêu.",
        "keywords": "hình thức ưu tiên,quy định áp dụng",
        "weight": 1.0,
        "source_id": "chunk-d830f682b07ebeb668d54551a6209b96",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485727
      },
      {
        "src_id": "Thí sinh Chưa Trúng tuyển hoặc Chưa Xác nhận Nhập học",
        "tgt_id": "Đơn vị Đào tạo",
        "description": "Thí sinh đăng ký xét tuyển đợt bổ sung theo kế hoạch và hướng dẫn của đơn vị đào tạo.",
        "keywords": "hướng dẫn,đăng ký theo kế hoạch",
        "weight": 1.0,
        "source_id": "chunk-cf425f7ca685593f88901f2f6d924893",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485565
      },
      {
        "src_id": "Phương thức tuyển sinh",
        "tgt_id": "Đơn vị đào tạo",
        "description": "Đơn vị đào tạo thông báo xét tuyển sớm đối với một số phương thức tuyển sinh.",
        "keywords": "thực hiện xét tuyển theo phương thức",
        "weight": 1.0,
        "source_id": "chunk-d70df8c903fddbcbfa9aedc2b549731f",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775486709
      },
      {
        "src_id": "Chế Độ Lưu Trữ",
        "tgt_id": "Đơn Vị",
        "description": "Đơn vị đào tạo chịu trách nhiệm thực hiện chế độ lưu trữ đối với tài liệu liên quan tuyển sinh.",
        "keywords": "quản lý hồ sơ,trách nhiệm",
        "weight": 1.0,
        "source_id": "chunk-99f0cf87ddf1406829eba421dbb9a9cc",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775486485
      },
      {
        "src_id": "Danh sách thí sinh trúng tuyển",
        "tgt_id": "Đơn vị đào tạo",
        "description": "Đơn vị đào tạo quyết định danh sách thí sinh trúng tuyển vào các nhóm ngành/ngành và chương trình đào tạo.",
        "keywords": "phân bổ vào,quyết định",
        "weight": 1.0,
        "source_id": "chunk-3f8b3d332cf0c347e8de3d57dc270374",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485141
      },
      {
        "src_id": "Đơn vị đào tạo",
        "tgt_id": "đăng ký dự tuyển",
        "description": "Đơn vị đào tạo tổ chức cho thí sinh thực hiện đăng ký dự tuyển theo điều khoản.",
        "keywords": "thủ tục,triển khai",
        "weight": 1.0,
        "source_id": "chunk-4b93cbd5d0914f2cef5a210a16b4bbf5",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775486327
      },
      {
        "src_id": "Các Chứng Chỉ Ngoại Ngữ Đáp Ứng Điều Kiện Chuẩn Đầu Ra",
        "tgt_id": "Phòng Đào Tạo (P.ĐT)",
        "description": "Phòng Đào tạo gửi thông tin tới các đơn vị và sinh viên về các chứng chỉ ngoại ngữ (tiếng Anh) đáp ứng chuẩn đầu ra.",
        "keywords": "truyền đạt thông tin",
        "weight": 1.0,
        "source_id": "chunk-1a3df01c18894f70ba1089c4742063c5",
        "file_path": "..\\..\\data\\data_1000_chunk_512.json",
        "created_at": 1775554198
      },
      {
        "src_id": "Công bố điểm trúng tuyển",
        "tgt_id": "Đơn vị đào tạo",
        "description": "Đơn vị đào tạo công bố điểm trúng tuyển (và các điều kiện, tiêu chí phụ nếu có).",
        "keywords": "công bố thông tin",
        "weight": 1.0,
        "source_id": "chunk-3f8b3d332cf0c347e8de3d57dc270374",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485143
      },
      {
        "src_id": "Trách Nhiệm Giải Trình",
        "tgt_id": "Đơn Vị Đào Tạo",
        "description": "Đơn vị đào tạo có trách nhiệm báo cáo theo yêu cầu của ĐHQGHN, các cơ quan quản lý nhà nước và giải trình với xã hội về các vấn đề lớn gây bức xúc cho người dân.",
        "keywords": "báo cáo,giải trình",
        "weight": 1.0,
        "source_id": "chunk-6bfc5f2ad22b00d8a493668fdba2fd14",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775486196
      },
      {
        "src_id": "Điều 2",
        "tgt_id": "Đơn vị đào tạo",
        "description": "Điều 2 giải thích khái niệm “Đơn vị đào tạo”.",
        "keywords": "giải thích từ ngữ,định nghĩa",
        "weight": 1.0,
        "source_id": "chunk-39701be07619a29470685a24ef242d87",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485786
      },
      {
        "src_id": "Chế độ báo cáo",
        "tgt_id": "Quy định, quy trình (nếu có) và các văn bản hướng dẫn tuyển sinh của đơn vị đào tạo",
        "description": "Chế độ báo cáo yêu cầu gửi nhóm tài liệu quy định, quy trình và văn bản hướng dẫn tuyển sinh của đơn vị đào tạo.",
        "keywords": "thành phần hồ sơ,tài liệu hướng dẫn",
        "weight": 1.0,
        "source_id": "chunk-5ef7502b5fff13cfaf706ccf8f094af6",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775486456
      },
      {
        "src_id": "Xét tuyển thẳng",
        "tgt_id": "Đơn vị đào tạo",
        "description": "Đơn vị đào tạo tổ chức xét tuyển thẳng cho những thí sinh đủ điều kiện.",
        "keywords": "triển khai,tổ chức",
        "weight": 1.0,
        "source_id": "chunk-4b93cbd5d0914f2cef5a210a16b4bbf5",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775486331
      },
      {
        "src_id": "hình thức trực tuyến hoặc trực tiếp",
        "tgt_id": "đăng ký dự tuyển",
        "description": "Đăng ký dự tuyển được thực hiện bằng hình thức trực tuyến hoặc trực tiếp tại đơn vị đào tạo.",
        "keywords": "hình thức,kênh thực hiện",
        "weight": 1.0,
        "source_id": "chunk-4b93cbd5d0914f2cef5a210a16b4bbf5",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775486331
      },
      {
        "src_id": "Đơn vị đào tạo",
        "tgt_id": "Đề án Tuyển sinh",
        "description": "Đơn vị đào tạo thông báo tuyển sinh kèm theo công bố đề án tuyển sinh.",
        "keywords": "công bố,thông báo kèm theo",
        "weight": 1.0,
        "source_id": "chunk-73e274f4a5ed1f38ed08014e717a6f92",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485520
      },
      {
        "src_id": "Quy trình đăng ký dự tuyển",
        "tgt_id": "Thí sinh",
        "description": "Quy trình đăng ký dự tuyển hướng đến thí sinh và cung cấp các thông tin cần thiết khác.",
        "keywords": "hướng dẫn thực hiện,thông tin cần thiết",
        "weight": 1.0,
        "source_id": "chunk-0d6008bd889a0ebc91d42d3a06f83f83",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485496
      },
      {
        "src_id": "n",
        "tgt_id": "Đơn vị đào tạo",
        "description": "n là mã số quy ước thống nhất được dùng trong đơn vị đào tạo.",
        "keywords": "phạm vi sử dụng,định danh",
        "weight": 1.0,
        "source_id": "chunk-18679ecca078f74da86923a647f33b04",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485756
      },
      {
        "src_id": "Chuyên viên Ban Đào tạo",
        "tgt_id": "Thư ký",
        "description": "Chuyên viên Ban Đào tạo đảm nhiệm vai trò Thư ký của Ban Chỉ đạo tuyển sinh.",
        "keywords": "vai trò,đảm nhiệm",
        "weight": 1.0,
        "source_id": "chunk-dccd9d905892f60251e114b78ae49b4c",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485033
      },
      {
        "src_id": "Danh sách thí sinh đủ điều kiện trúng tuyển",
        "tgt_id": "Đơn vị đào tạo",
        "description": "Đơn vị đào tạo công bố và tải danh sách thí sinh đủ điều kiện trúng tuyển lên hệ thống để xử lý nguyện vọng.",
        "keywords": "công bố và tải dữ liệu",
        "weight": 1.0,
        "source_id": "chunk-d70df8c903fddbcbfa9aedc2b549731f",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775486730
      },
      {
        "src_id": "Thông tin cá nhân",
        "tgt_id": "Trách nhiệm của thí sinh",
        "description": "Thí sinh phải cung cấp đầy đủ và bảo đảm tính chính xác thông tin cá nhân trong đăng ký dự tuyển.",
        "keywords": "cung cấp thông tin,tính chính xác",
        "weight": 1.0,
        "source_id": "chunk-bf836ea6db4d8badfb97990a59aa4543",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485483
      },
      {
        "src_id": "Đăng ký dự tuyển",
        "tgt_id": "Đơn vị đào tạo",
        "description": "Đơn vị đào tạo tạo điều kiện để thí sinh có nguyện vọng được đăng ký dự tuyển.",
        "keywords": "hỗ trợ quy trình",
        "weight": 1.0,
        "source_id": "chunk-c214b57125a6e684d66bb9c16816dffa",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485391
      },
      {
        "src_id": "Thông tin khu vực",
        "tgt_id": "Trách nhiệm của thí sinh",
        "description": "Thí sinh phải cung cấp đầy đủ và bảo đảm tính chính xác thông tin khu vực trong đăng ký dự tuyển.",
        "keywords": "cung cấp thông tin,tính chính xác",
        "weight": 1.0,
        "source_id": "chunk-bf836ea6db4d8badfb97990a59aa4543",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485484
      },
      {
        "src_id": "Điều 13. Tổ chức đăng ký và xét tuyển thẳng",
        "tgt_id": "Đơn vị đào tạo",
        "description": "Điều 13 quy định đơn vị đào tạo tổ chức đăng ký và tổ chức xét tuyển thẳng cho thí sinh thuộc đối tượng.",
        "keywords": "thực hiện,tổ chức",
        "weight": 1.0,
        "source_id": "chunk-4b93cbd5d0914f2cef5a210a16b4bbf5",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775486337
      },
      {
        "src_id": "Kiểm tra Thông tin và Hồ sơ Minh chứng",
        "tgt_id": "Đơn vị Đào tạo",
        "description": "Đơn vị đào tạo phải kiểm tra thông tin và hồ sơ minh chứng khi thí sinh nhập học.",
        "keywords": "kiểm soát điều kiện,thẩm định",
        "weight": 1.0,
        "source_id": "chunk-1cb8513b18d53e7800fe51928b1efe1c",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485497
      },
      {
        "src_id": "Trang Thông tin Điện tử của Đơn vị",
        "tgt_id": "Đơn vị đào tạo",
        "description": "Đơn vị đào tạo công bố thông tin tuyển sinh trên trang thông tin điện tử của đơn vị.",
        "keywords": "kênh công bố,đăng tải",
        "weight": 1.0,
        "source_id": "chunk-73e274f4a5ed1f38ed08014e717a6f92",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "created_at": 1775485522
      }
    ],
    "chunks": [
      {
        "reference_id": "1",
        "content": "h theo các quy định của nhà nước;\n    c.  Cung cấp đầy đủ thông tin, tư vấn và hướng dẫn thí sinh, không để thí sinh đăng ký dự tuyển vào một nhóm ngành/ngành, chương trình đào tạo hay theo một phương thức tuyển sinh của đơn vị đào tạo mà không đủ điều kiện;\n    d.  Bảo đảm quy trình xét tuyển chính xác, công bằng, khách quan; thực hiện các cam kết theo đề án tuyển sinh đã công bố;\n    đ. Kiểm tra thông tin và hồ sơ minh chứng khi thí sinh nhập học, bảo đảm tất cả thí sinh nhập học phải đủ điều kiện trúng tuyển;\n    e.  Giải quyết đơn thư phản ánh, khiếu nại, tố cáo liên quan tới công tác xét tuyển của đơn vị đào tạo theo quy định của pháp luật.",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "chunk_id": "chunk-1cb8513b18d53e7800fe51928b1efe1c"
      },
      {
        "reference_id": "1",
        "content": "áo xét tuyển đợt bổ sung (nếu có);\n    h. Báo cáo tổng kết công tác tuyển sinh của đơn vị trước ngày 31/10;\n\n2.  Chế độ lưu trữ\n\nĐơn vị đào tạo có trách nhiệm lưu trữ, bảo quản an toàn các tài liệu liên quan tới công tác tuyển sinh theo các quy định do Bộ GD&ĐT ban hành.\n\n    a.  Quyết định trúng tuyển, quyết định công nhận sinh viên là tài liệu lưu trữ được bảo quản vĩnh viễn tại đơn vị đào tạo;\n    b.  Tài liệu khác liên quan đến tuyển sinh, đào tạo được lưu trữ, bảo quản trong suốt quá trình đào tạo;\n    c.  Việc tiêu hủy tài liệu liên quan tuyển sinh, đào tạo hết thời gian lưu trữ được thực hiện theo quy định hiện hành của nhà nước.",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "chunk_id": "chunk-99f0cf87ddf1406829eba421dbb9a9cc"
      },
      {
        "reference_id": "1",
        "content": "yển sinh và cam kết trách nhiệm của đơn vị đào tạo.\n\n3.  Đơn vị đào tạo thông báo tuyển sinh kèm theo công bố đề án tuyển sinh trên trang thông tin điện tử của đơn vị, cổng thông tin tuyển sinh của ĐHQGHN và qua các hình thức phù hợp khác trước khi mở đăng ký dự tuyển của đợt tuyển sinh đầu tiên ít nhất 30 ngày; trường hợp điều chỉnh, bổ sung (nếu có) trước ít nhất 15 ngày.",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "chunk_id": "chunk-73e274f4a5ed1f38ed08014e717a6f92"
      },
      {
        "reference_id": "1",
        "content": "van_ban | quyet_dinh_1328_quy_che_tuyen_sinh_vnu | 2023-04-18\n\n## Điều 24. Chế độ báo cáo và lưu trữ\n\n1.  Chế độ báo cáo \nHằng năm, HĐTS các đơn vị gửi báo cáo Ban Chỉ đạo tuyển sinh (qua Ban Đào tạo):\n    a.  Quyết định thành lập HĐTS và các tiểu ban chuyên môn;\n    b.  Đề án tuyển sinh (theo mẫu tại Phụ lục V Quy chế này) trước khi công bố ít nhất 10 ngày;\n    c.  Quy định, quy trình (nếu có) và các văn bản hướng dẫn tuyển sinh của đơn vị đào tạo;\n    d.  Kết quả lọc ảo trước khi nhập kết quả xét tuyển lên hệ thống lọc ảo (lần cuối); điểm trúng tuyển theo nhóm ngành/ngành, chương trình đào tạo trước khi công bố kết quả trúng tuyển;\n    đ. Danh sách thí sinh trúng tuyển (dự kiến) theo các phương thức tuyển sinh trước khi ra quyết định công nhận trúng tuyển chính thức;\n    e.  Quyết định trúng tuyển và danh sách thí sinh trúng tuyển theo các phương thức tuyển sinh; Danh sách nhập học theo các phương thức tuyển sinh;\n    g.  Đối với các ngành chưa tuyển đủ chỉ tiêu trong đợt 1, đơn vị báo cáo Ban Chỉ đạo tuyển sinh xem xét, phê duyệt kế hoạch xét tuyển đợt bổ sung trước khi ra thông báo xét tuyển đợt bổ sung (nếu có);\n    h. Báo cáo tổng kết công tác tuyển sinh của đơn vị trước ngày",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "chunk_id": "chunk-5ef7502b5fff13cfaf706ccf8f094af6"
      },
      {
        "reference_id": "1",
        "content": "định việc tiếp nhận thí sinh vào học hoặc bảo lưu kết quả tuyển sinh để thí sinh vào học sau.\n4.  Thí sinh đã xác nhận nhập học tại một đơn vị đào tạo không được tham gia xét tuyển ở nơi khác hoặc ở các đợt xét tuyển bổ sung, trừ trường hợp được đơn vị đào tạo cho phép.\n5.  Ký và đóng dấu giấy báo thí sinh trúng tuyển\n- Hiệu trưởng các trường đại học thành viên ký và đóng dấu giấy báo thí sinh trúng tuyển vào trường.\n- Trưởng Ban Đào tạo ký và đóng dấu giấy báo thí sinh trúng tuyển vào các trường/khoa trực thuộc.",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "chunk_id": "chunk-1f39a0ff78c35fa4b16ff781cf5edaf3"
      },
      {
        "reference_id": "1",
        "content": "m các môn học xét tuyển tương đương với yêu cầu xét tuyển thí sinh có chứng chỉ A-Level Quy định tại Quy chế này)_ kết hợp với kiểm tra kiến thức chuyên môn và năng lực Tiếng Việt hoặc năng lực ngoại ngữ _(tùy theo yêu cầu của ngành học để xét tuyển)_ đáp ứng quy định hiện hành của Bộ GD&ĐT và của ĐHQGHN.\n\n4.  Đơn vị đào tạo quy định hình thức ưu tiên xét tuyển khác đối với các trường hợp sau đây:\n\n    a.  Thí sinh quy định tại khoản 1, 2 Điều này dự tuyển vào các ngành theo nguyện vọng (không dùng quyền ưu tiên tuyển thẳng);\n\n    b.  Thí sinh đoạt giải khuyến khích trong kỳ thi chọn học sinh giỏi quốc gia; thí sinh đoạt giải tư trong cuộc thi khoa học, kỹ thuật cấp quốc gia dự tuyển vào ngành phù hợp với môn thi hoặc nội dung đề tài dự thi đã đoạt giải; thời gian đoạt giải không quá 3 năm tính tới thời điểm xét tuyển;\n    \n    c.  Thí sinh đoạt huy chương vàng, bạc, đồng các giải thể dục thể thao cấp quốc gia tổ chức một lần trong năm và thí sinh được Tổng cục Thể dục thể thao có quyết định công nhận là kiện tướng quốc gia dự tuyển vào các ngành thể dục thể thao phù hợp; thời gian đoạt giải không quá 4 năm tính tới thời điểm xét tuyển;\n\n    d.  Thí sinh đoạt giải chính thức trong",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "chunk_id": "chunk-d830f682b07ebeb668d54551a6209b96"
      },
      {
        "reference_id": "1",
        "content": "van_ban | quyet_dinh_1328_quy_che_tuyen_sinh_vnu | 2023-04-18\n\n## Điều 19. Trách nhiệm của các bên liên quan trong công tác xét tuyển\n\n1.  Trách nhiệm của thí sinh\n    a.  Tìm hiểu kỹ thông tin tuyển sinh của các đơn vị đào tạo, không đăng ký nguyện vọng vào những ngành, chương trình đào tạo hay phương thức tuyển sinh mà không đủ điều kiện;\n    b.  Cung cấp đầy đủ và bảo đảm tính chính xác của tất cả thông tin đăng ký dự tuyển, bao gồm cả thông tin cá nhân, thông tin khu vực và đối tượng ưu tiên (nếu có), nguyện vọng đăng ký; tính xác thực của các giấy tờ minh chứng;\n    c.  Đồng ý để đơn vị đào tạo mà mình dự tuyển được quyền sử dụng thông tin, dữ liệu cần thiết phục vụ cho công tác xét tuyển;\n    d.  Hoàn thành thanh toán lệ phí tuyển sinh trước khi kết thúc thủ tục đăng ký dự tuyển.\n\n2.  Trách nhiệm của đơn vị đào tạo\n    a.  Cung cấp đầy đủ, đúng định dạng và bảo đảm tính xác thực của thông tin, dữ liệu tuyển sinh lên hệ thống theo hướng dẫn của Bộ GD&ĐT;\n    b.  Quy định (hoặc thống nhất với các đơn vị đào tạo khác) về mức thu, phương thức thu và sử dụng lệ phí dịch vụ tuyển sinh theo các quy định của nhà nước;\n    c.  Cung cấp đầy đủ thông tin, tư vấn và hướng dẫn thí sinh, k",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "chunk_id": "chunk-bf836ea6db4d8badfb97990a59aa4543"
      },
      {
        "reference_id": "1",
        "content": "van_ban | quyet_dinh_1328_quy_che_tuyen_sinh_vnu | 2023-04-18\n\n## Chương I QUY ĐỊNH CHUNG\n\n**Điều 1. Phạm vi điều chỉnh và đối tượng áp dụng**\n\n1.  Quy chế này quy định những nguyên tắc, yêu cầu, tiêu chuẩn, quy trình, quy định cụ thể về xét tuyển, quyền hạn và trách nhiệm của các bên liên quan trong công tác tuyển sinh đại học chính quy tại Đại học Quốc gia Hà Nội (ĐHQGHN);\n2.  Quy chế này áp dụng đối với các đơn vị, tổ chức, cá nhân có liên quan trong công tác tuyển sinh đại học chính quy vào các chương trình đào tạo do Giám đốc ĐHQGHN, Hiệu trưởng các trường thành viên cấp bằng và các chương trình đào tạo liên kết với cơ sở giáo dục nước ngoài do ĐHQGHN cấp bằng, hai bên cùng cấp bằng (_không áp dụng đối với tuyển sinh các chương trình đào tạo liên kết do các cơ sở giáo dục nước ngoài cấp bằng)_.\n\n## Điều 2. Giải thích từ ngữ\n\nTrong văn bản này, các từ ngữ dưới đây được hiểu như sau:\n\n1.  Phạm vi tuyển sinh là các chương trình, ngành, nhóm ngành và lĩnh vực được tổ chức tuyển sinh trong một đợt hoặc theo một phương thức tuyển sinh nhất định.\n2.  Đơn vị đào tạo là trường đại học thành viên, trường/khoa trực thuộc ĐHQGHN có chức năng nhiệm vụ tổ chức đào tạo đại học.\n3.  Dự tuyển",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "chunk_id": "chunk-39701be07619a29470685a24ef242d87"
      },
      {
        "reference_id": "1",
        "content": "ệp (trên tổng số nhập học) và tỉ lệ có việc làm phù hợp trình độ chuyên môn của sinh viên tốt nghiệp theo Phụ lục V của Quy chế này;\n\n    b.  Thông tin đầy đủ về chi phí đào tạo, mức thu học phí, mức thu dịch vụ tuyển sinh và khoản thu dịch vụ khác cho lộ trình cả khóa học, từng năm học; chính sách học bổng, miễn giảm học phí, hỗ trợ tài chính, chỗ ở ký túc xá và các chính sách ưu đãi, hỗ trợ khác dành cho người học;\n    \n    c.  Kế hoạch tuyển sinh và phạm vi tuyển sinh các đợt trong năm (trong đó đợt 1 tuyển sinh phải phù hợp với kế hoạch chung do Bộ GD&ĐT ban hành), gồm cả quy định về đối tượng và điều kiện tuyển sinh, phương thức tuyển sinh, tổ hợp xét tuyển và chỉ tiêu tuyển sinh đối với các ngành, chương trình đào tạo; quy trình, thủ tục đăng ký dự tuyển và các thông tin cần thiết khác cho thí sinh; Riêng các chương trình đào tạo tài năng, chất lượng cao phải có quy định về điều kiện về ngoại ngữ; các chương trình đào tạo thí điểm phải ghi chú cụ thể, rõ ràng, đầy đủ thông tin để không gây hiểu lầm cho thí sinh.\n    \n    d.  Các phương án xử lý rủi ro khi triển khai công tác tuyển sinh và cam kết trách nhiệm của đơn vị đào tạo.\n\n3.  Đơn vị đào tạo thông báo tuyển sinh kèm the",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "chunk_id": "chunk-0d6008bd889a0ebc91d42d3a06f83f83"
      },
      {
        "reference_id": "1",
        "content": "van_ban | quyet_dinh_1328_quy_che_tuyen_sinh_vnu | 2023-04-18\n\n**Chương III**\n\n# TỔ CHỨC THỰC HIỆN\n\n## Điều 20. Tổ chức, nhiệm vụ và quyền hạn của ĐHQGHN\n\n1.  Ban hành kế hoạch tuyển sinh chung và xây dựng các văn bản hướng dẫn về công tác tuyển sinh tại ĐHQGHN;\n2.  Giám đốc ĐHQGHN ra quyết định thành lập Ban Chỉ đạo tuyển sinh của ĐHQGHN để chỉ đạo các đơn vị thuộc ĐHQGHN trong công tác tuyển sinh đảm bảo đúng quy định của Quy chế này.\n    2.1.  Thành phần Ban Chỉ đạo tuyển sinh gồm có:\n        a.  Trưởng ban: Đại diện Ban Giám đốc;\n        b.  Phó Trưởng ban: Trưởng ban Đào tạo;\n        c.  Các uỷ viên: Đại diện lãnh đạo Ban Đào tạo, Ban Thanh tra và Pháp chế, Văn phòng ĐHQGHN; đại diện lãnh đạo các đơn vị đào tạo, Giám đốc Trung tâm Khảo thí ĐHQGHN;\n        d.  Thư ký: Chuyên viên Ban Đào tạo.\n\n        _Những người có người thân (con, vợ/chồng, anh, chị, em ruột của mình và của chồng/vợ) dự thi hay đăng ký xét tuyển vào ĐHQGHN không được tham gia Ban Chỉ đạo tuyển sinh._\n\n    2.2.  Nhiệm vụ và quyền hạn của Ban Chỉ đạo tuyển sinh\n\n        a.  Chỉ đạo và tổ chức các hoạt động truyền thông, tư vấn tuyển sinh của ĐHQGHN;\n        b.  Chỉ đạo và tổ chức triển khai công tác tuyển sinh",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "chunk_id": "chunk-dccd9d905892f60251e114b78ae49b4c"
      },
      {
        "reference_id": "1",
        "content": "hợp rủi ro.\n\n2.  Bình đẳng giữa các đơn vị đào tạo\n    a.  Về hợp tác: Hợp tác bình đẳng nhằm nâng cao chất lượng và hiệu quả tuyển sinh, đồng thời mang lại lợi ích tốt nhất cho thí sinh;\n    b.  Về cạnh tranh: Cạnh tranh trung thực, công bằng và lành mạnh trong tuyển sinh theo quy định của pháp luật về cạnh tranh.\n3.  Minh bạch đối với xã hội\n    a.  Về minh bạch thông tin: Đơn vị đào tạo có trách nhiệm công bố thông tin tuyển sinh đầy đủ, rõ ràng và kịp thời qua các phương tiện truyền thông phù hợp để xã hội, cơ quan quản lý nhà nước và ĐHQGHN cùng giám sát;\n    b.  Về trách nhiệm giải trình: Đơn vị đào tạo có trách nhiệm báo cáo theo yêu cầu của ĐHQGHN, các cơ quan quản lý nhà nước và giải trình với xã hội về những vấn đề lớn, gây bức xúc cho người dân.",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json",
        "chunk_id": "chunk-6bfc5f2ad22b00d8a493668fdba2fd14"
      },
      {
        "reference_id": "2",
        "content": "https://uet.vnu.edu.vn/cac-chung-chi-ngoai-ngu-dap-ung-dieu-kien-chuan-dau-ra/\n\nCác chứng chỉ ngoại ngữ đáp ứng điều kiện chuẩn đầu ra Căn cứ Quy chế đào tạo đại học ban hành theo Quyết định số 5115/QĐ-ĐHQGHN ngày 25/12/2014 của Giám đốc Đại học Quốc gia Hà Nội; Căn cứ Công văn số 70/ĐHQGHN-ĐT ngày 12/01/2021 về việc “Danh sách các cơ sở cấp chứng chỉ Ngoại ngữ (tiếng Anh) theo Khung năng lực ngoại ngữ 6 bậc dùng cho Việt Nam” của Đại học Quốc gia Hà Nội; Phòng Đào tạo (P.ĐT) trân trọng gửi đến các đơn vị trong trường và sinh viên đại học hệ chính quy thông tin về các chứng chỉ Ngoại ngữ (tiếng Anh) đáp ứng điều kiện về chuẩn đầu ra như sau: 1. Bảng tham chiếu mức điểm tối thiểu một số chứng chỉ Tiếng Anh tương đương bậc 3 và bậc 4 theo Khung năng lực Ngoại ngữ 6 bậc dùng cho Việt Nam Khung năng lực ngoại ngữ VN IELTS TOEFL TOEIC (4 kỹ năng) Cambridge Tests Vietnamese Standardized Test of English Proficiency Bậc 3 4.5 460 ITP 42 iBT Reading 275 Listening 275 Speaking 120 Writing 120 KET (Distinction 140) PET (Pass 140) FCE (Level B1-140) VSTEP.3-5 (4.0) Bậc 4 5.5 543 ITP 72 iBT Reading 385 Listening 400 Speaking 160 Writing 150 KET (Distinction 160) PET (Pass 160) FCE (Level B1-160",
        "file_path": "..\\..\\data\\data_1000_chunk_512.json",
        "chunk_id": "chunk-1a3df01c18894f70ba1089c4742063c5"
      }
    ],
    "references": [
      {
        "reference_id": "1",
        "file_path": "..\\..\\data\\quyet_dinh_1328_chunks.json"
      },
      {
        "reference_id": "2",
        "file_path": "..\\..\\data\\data_1000_chunk_512.json"
      }
    ]
  },
  "metadata": {
    "query_mode": "hybrid",
    "keywords": {
      "high_level": [
        "Trách nhiệm của đơn vị đào tạo",
        "Phát hiện thông tin không chính xác",
        "Quá trình đăng ký tuyển sinh",
        "Quy định tuyển sinh",
        "Xử lý vi phạm thông tin đăng ký"
      ],
      "low_level": [
        "đơn vị đào tạo",
        "thông tin không chính xác",
        "đăng ký tuyển sinh",
        "tuyển sinh"
      ]
    },
    "processing_info": {
      "total_entities_found": 75,
      "total_relations_found": 187,
      "entities_after_truncation": 10,
      "relations_after_truncation": 42,
      "merged_chunks_count": 32,
      "final_chunks_count": 12
    }
  },
  "llm_response": {
    "content": "Theo quy định về trách nhiệm của **đơn vị đào tạo**, trong công tác tuyển sinh (bao gồm việc cung cấp và xử lý thông tin liên quan đến xét tuyển), đơn vị đào tạo có các trách nhiệm sau khi phát hiện thông tin **không chính xác** trong quá trình đăng ký/tuyển sinh:\n\n- **Bảo đảm tính xác thực của thông tin, dữ liệu tuyển sinh** mà đơn vị cung cấp và/hoặc đưa lên hệ thống theo hướng dẫn của Bộ GD&ĐT: đơn vị đào tạo phải cung cấp “đầy đủ, đúng định dạng và bảo đảm tính xác thực” của thông tin/dữ liệu tuyển sinh lên hệ thống.  \n- **Không để thí sinh đăng ký dự tuyển khi chưa đủ điều kiện**: đơn vị đào tạo phải cung cấp đầy đủ thông tin, tư vấn và hướng dẫn thí sinh, “không để thí sinh đăng ký” vào nhóm ngành/ngành/chương trình/phương thức tuyển sinh của đơn vị mà **không đủ điều kiện**.  \n- **Kiểm tra thông tin và hồ sơ minh chứng** tại giai đoạn nhập học: đơn vị đào tạo phải kiểm tra thông tin và hồ sơ minh chứng khi thí sinh nhập học, bảo đảm các thí sinh nhập học “phải đủ điều kiện trúng tuyển”.\n\nNgoài ra, đơn vị đào tạo còn phải **giải quyết các đơn thư phản ánh, khiếu nại, tố cáo** liên quan đến công tác xét tuyển của đơn vị theo quy định của pháp luật.\n\n### References\n\n* [1] ..\\..\\data\\quyet_dinh_1328_chunks.json",
    "response_iterator": null,
    "is_streaming": false
  }
}
```
