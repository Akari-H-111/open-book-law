# 繁體中文用語表

專案的繁體中文文件依這張表用字。讀者是台灣的法律工作者和法律系學生，所以優先用官方文件和法學教學的說法。

「避免」欄會由檢查程式掃描。原文引用和專有名稱不受這張表限制，例如引用中國法資料時可以保留原文。

## 考試與法律

| 用這個 | English | 避免 | 說明 |
|---|---|---|---|
| 司法官暨律師考試第一試（簡稱「司律一試」） | first stage of the Judicial Officer and Bar Examination | 法考、律考 | 考選部公告用「第一試」 |
| 標準答案、更正答案 | standard answer, corrected answer | 參考答案、官方解答 | 考選部的用語 |
| 一律給分 | points awarded to all | 送分 | 口語可以說送分，文件不用 |
| 法條、條文 | statute article | 法条、法律条文 | |
| 條、項、款、目 | article, paragraph, subparagraph, item | | 引用格式：民法第 184 條第 1 項前段 |
| 但書、準用 | proviso, applied mutatis mutandis | | 法學常用語 |
| 修正公布、施行 | promulgation of an amendment, entry into force | 生效（泛指時可用） | 這兩個日期可能不同，要分開寫 |
| 法條沿革 | legislative history of an article | 修法历史 | 全國法規資料庫的用語 |
| 現行法 | current law | 現行法律（可並用） | |
| 大法官解釋、憲法法庭判決 | Grand Justice interpretation, Constitutional Court judgment | | 2022 年起為憲法法庭判決 |
| 判決、裁定、裁判 | judgment, ruling, decision | | 三者範圍不同，不要混用 |
| 法律見解 | legal opinion of a court | 法律观点 | |
| 判決被推翻（美國法脈絡） | overruled | 被否决 | 第一次出現時附英文 overruled |
| 仍具效力的法律 | good law | 好法律 | 第一次出現時附英文 good law |

## 資料與模型

| 用這個 | English | 避免 | 說明 |
|---|---|---|---|
| 資料、資料集 | data, dataset | 數據、數據集 | |
| 語料 | corpus | | 這裡指法條或判決段落的集合 |
| 檢索、檢索器 | retrieval, retriever | 搜索、召回（作動詞時） | |
| 召回率 | recall | 查全率 | 第一次出現時說明定義 |
| 準確率 | accuracy | 正確率（可並用） | |
| 大型語言模型 | large language model | 大模型 | |
| 閱讀模型 | reader | 读者模型 | 本專案中負責讀資料並作答的模型 |
| 向量、嵌入 | vector, embedding | | |
| 微調 | fine-tuning | 精調 | |
| 基線 | baseline | | |
| 重現 | reproduce | 復現 | |
| 訓練集、驗證集、測試集 | training, validation and test set | | |
| 人工智慧 | artificial intelligence | 人工智能 | |
| 演算法 | algorithm | 算法 | |
| 程式、程式碼 | program, code | 程序（指電腦程式時）、代碼 | 法律的「程序」不受影響，檢查程式只報告，由人判斷 |
| 軟體、硬體 | software, hardware | 軟件、硬件 | |
| 網路 | network, internet | 網絡 | |
| 預設 | default | 默認 | |
| 品質 | quality | 質量 | |
| 資訊 | information | 信息 | |
| 伺服器 | server | 服務器 | |
| 使用者 | user | 用戶 | |

## 錯誤類型

報表的兩種語言都用這些名稱。

| 代碼 | 繁體中文 | English |
|---|---|---|
| `retrieval` | 查不到 | retrieval |
| `reading` | 查到但讀錯 | reading |
| `out-of-library` | 圖書館裡沒有 | out of library |
| `law-changed` | 法律已改變 | law changed |
| `key-dispute` | 答案有爭議 | key dispute |
| `parse` | 題目解析錯誤 | parse |
| `other` | 其他 | other |
