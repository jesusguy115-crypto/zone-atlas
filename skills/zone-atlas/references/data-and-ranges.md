# 数据与范围

## NBA

NBA球员ID与别名见assets/players.json；目录不完整时查官方资料，不模糊匹配。数据来自SportsDataverse GitHub release，年份是结束年（2026=2025-26）。season_type_id 2=常规赛，4=季后赛，3是全明星，不纳入。

```sh
python scripts/fetch_data.py --person-id 2544 --years 2026 --cache <已有NBA缓存> --output <全季CSV>
python scripts/select_range.py --shots <全季CSV> --player-id 2544 --seasons 2026 --phases 4 --output <季后赛CSV>
```

优先复用已有`shots_2026.parquet`和`nba_schedule_2026.parquet`。fetch_data会从发布清单发现文件并关联比赛日期；已缓存的坐标无需重下。源：

- https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/nba_stats_shots
- https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/nba_stats_schedules

NBA原始x_legacy/y_legacy单位十分之一英尺；世界点x=-x_legacy/10、y=y_legacy/10，篮圈为0。现代NBA三分半径23.75ft、侧段22ft；五区与十区共用zone_geometry.py。1996-97三分线较短，先增加对应几何并验证后才能制作，不假定现代模板适用全部历史年代。

## 范围目录

所有范围输入先按同一player_id/season/season_type_id筛选。NBA官方比赛日志/盒分或CBA球员逐场表用于确认出场，零分钟DNP不算出场，实际上场但零出手要算。实际出场目录JSON：

```json
[{"game_id":"0042500171","game_date":"2026-04-18","person_id":2544,"season":2026,"season_type_id":"4","played":true}]
```

```sh
python scripts/select_range.py --shots <含日期的全季CSV> --player-id 2544 --seasons 2026 --phases 4 --games <实际出场目录.json> --first-game 1 --last-game 10 --output <选中CSV>
```

输出selection.json中的selected_game_ids、games、attempts、made传给job；包含0出手的出场时，job仍记录选中比赛数及所有ID。未经目录验证不得把有坐标的前10场冒充实际出场前10场。指定比赛可用`--game-ids`，总决赛示例0042500401至0042500405必须先在赛程确认存在及球员出场。轮次按赛程/官方系列赛目录，不能只凭日期猜。

## CBA：静态图无需投篮飞行时间

先查共享本机缓存的 `cba/2025-26/regular/cba_league_2026.parquet`，该季已保存420场、56,584条真实坐标。仅球员subset及赛程日期即可制作静态图；**不为静态图额外抓全季PbP来分配动画时间**。ordinal范围仍要源站实际出场目录，基准仍要全联盟坐标。

没有缓存时，通过用户已登录CBAstats正常页面/业务客户端获取。CBA身份与NBA不通用；leagueId10003，2025-26源站year=2025、seasonId200732、常规赛stageType1。其他赛季/阶段从页面实际响应发现，不猜ID；规范输出用season结束年和phase2/4。

已验证正常接口，示例在scripts/cba_browser_api.js：

- POST `/api/base/shoot-plot/games`，body是筛选对象**数组**，playerId筛球员赛程，teamId筛球队赛程。
- POST `/api/player-shot/shot-plot`，`{playerId:"21674",scheduleIds:[...]}`；去掉playerId获取指定比赛两队全部球员坐标。40场一批即取即存，单批失败保留其他批次。
- POST `/api/players/match-base-data-info/player`，传playerId、leagueIds、seasonId、seasonYears、stageType、stageTypes及dataType:"sum"，选取正确赛季/阶段的fga/fgM/thfga/thfgM/gamesPlayed。不要用场均舍入值或hotShootArea错误汇总替代精确统计。
- 全联盟用完整球队目录逐队取赛程，按scheduleId去重，获取双方所有球员坐标。不能假定任意球员的对手已涵盖全部球队；按当季全部已赛比赛核查覆盖。

从当前网页公开script/import及正常请求发现应用client及模块；旧hashed bundle会失效，不硬编码认证信息或破解付费。能用浏览器工具读取已登录页面就直接用；无访问权限时报告实际缺项。

原始行含pbpType/playerId/scheduleId/teamId/shotX/shotY，2PM/3PM为进，2Pm/3Pm为未中，大小写有意义。现代CBA已验证映射：x_m=(shotX-.5)×15，y_m=shotY×14-1.575；x_legacy=-x_m/.3048×10，y_legacy=y_m/.3048×10。**shotY>1可为远距离压哨，不截断。**

```sh
python scripts/prepare_cba_data.py league --batches <原始批次JSON列表> --season 2026 --phase 2 --output <CBA联盟parquet>
```

从规范化parquet筛球员，按赛程关联game_date写CSV，再交select_range.py。该parquet保留CBA联盟metadata，渲染器拒绝拿NBA联盟基准冒充CBA。现代FIBA28×15米、三分半径6.75米、侧段6.6米、篮下半径1.25米、禁区宽4.9米，球场绘制与分区统一；历史线规先核实。

## 资料、缺口与缓存

官方身高体重转cm/kg。年龄按范围结束日和生日计算；NBA/CBA球龄用实际参加过的联盟赛季数，不把其他联赛或整季缺席计入。确定赛季头像和队标，实时头像可能已换队。素材缓存键带playerId/年份/球队，保存公开来源URL与核验日期。

独立核验精确技术统计，保留重复坐标、不抖动、不去重。贺希宁2025-26常规赛官方613次出手、294中，但612条坐标、294中；缺1次未中。在job用expected_attempts612/made294，栏名设“坐标出手”，另记official_attempts613及missing_coordinate_attempts1，在交付说明差额。不能把该个案套到其他球员。

比赛目录、全联盟parquet、筛选CSV、个人资料、头像、队标、字体及job都即取即缓存；本机共享缓存路径优先，保留范围、日期、基准与校验记录。付费业务数据只本地保存，不发公开GitHub；不保存Cookie/Authorization/CSRF/密码/浏览器抓包。首次安装者需要自己的源站权限及缓存，不假装ZIP包含完整CBA数据库。
