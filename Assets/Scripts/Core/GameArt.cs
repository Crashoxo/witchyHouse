using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>村民走路表的列（＝面向）。</summary>
    public static class VillagerDir { public const int Down = 0, Side = 1, Up = 2; }

    /// <summary>
    /// 方向索引：0 南（下）起、每 45° 逆時針一格。
    /// 對應圖集的欄：south, south-east, east, north-east, north, north-west, west, south-west。
    /// </summary>
    public static class WitchDir { public const int South = 0, East = 2, North = 4, West = 6; }

    /// <summary>
    /// 遊戲美術的執行期載入器：把 Assets/Resources/ 底下的圖依路徑載進 Dictionary，
    /// 供背包圖示、貨架、顧客、UI 共用。
    ///
    /// ── 跟 Cocos 版的差別 ────────────────────────────────────────────
    /// 原本 Cocos 的 resources.load 是**非同步**的，所以 GameArt.ts 有一整套
    /// pending / jobDone() / onReady() 的計數與回呼機制，還要用 w8Seq 擋掉
    /// 「換裝的回呼晚於預載的回呼、把新造型蓋回舊的」這種競態。
    ///
    /// Unity 的 Resources.Load 是**同步**的 —— 上面那些全部不需要了，連同競態一起消失。
    /// 但 Ready / OnReady() 這兩個對外 API 特意保留（Ready 恆為已載入、OnReady 立刻執行），
    /// 這樣其他檔的呼叫端一行都不用改。
    ///
    /// ⚠️ 代價是切場景時會同步卡一下。目前 17MB 圖、又有分區載入，應該可接受；
    ///    真的卡了再換 Resources.LoadAsync + 協程，對外 API 不用動。
    /// </summary>
    public static class GameArt
    {
        // ──────────── 走圖排法（跟原專案一致）────────────

        /// <summary>村民走圖：4 欄（動畫幀）× 3 列（下／側／上）。單格大小由圖檔尺寸算出。</summary>
        const int VillagerCols = 4, VillagerRows = 3;

        static readonly string[] VillagerFiles =
        {
            "frog", "fox", "rabbit", "hedgehog", "witch",
            "deer", "broomwitch", "fairy", "traveler", "mage", "rabbitwitch",
        };

        /// <summary>表情動畫：檔名 → (單幀寬, 單幀高, 幀數)（橫向 strip）。</summary>
        static readonly Dictionary<string, (int W, int H, int N)> EmoteInfo = new()
        {
            ["emo18"] = (33, 30, 28), ["emo3"] = (29, 26, 29), ["emo2"] = (43, 30, 29),
            ["emo32"] = (57, 48, 28), ["emo51"] = (29, 55, 28),
        };

        static readonly string[] PortraitFiles =
        {
            "gnome", "witch", "elf", "forestboy", "badger", "fox",
            "hedgehog", "rabbit", "bear", "squirrel", "wolf", "mouse",
        };

        /// <summary>時鐘盤面零件（Resources/ui/clock 底下）：盤面／日月圖示／指針。</summary>
        static readonly string[] ClockFiles = { "face", "sun", "moon", "hand-hour", "hand-min", "hand-day" };

        /// <summary>季節圖標，索引＝TimeSystem.Season（0 春 … 3 冬）。</summary>
        static readonly string[] SeasonFiles = { "spring", "summer", "autumn", "winter" };

        const int CauldronFrameCount = 6;   // Resources/cauldron/f0..f5
        const int GatherFrameCount = 3;     // witch/gather1..3：彎腰伸手→捏起→起身舉起
        const int WaterFrameCount = 4;
        const int PickFrameCount = 4;

        static readonly string[] SoilFiles = { "soil-dry", "soil-wet" };

        /// <summary>花的走圖：6 欄（成長階段）× 2 列（第 0 列健康、第 1 列枯萎）。</summary>
        const int FlowerCols = 6, FlowerRows = 2;

        // ──────────── 花圃（8-bit 像素風）────────────

        /// <summary>
        /// 開關：true ＝ 花圃的土壤磚與花的成長／枯萎走圖改用 tools/gen_garden_plants.py 程式點陣畫的
        /// 8-bit 圖（Resources/garden8/）；false ＝ 退回原本的 garden/ 舊圖（一張都沒刪）。
        /// 開著但 garden8 裡缺圖（例如跑過 gen_garden_plants.py --restore），那張自動退回舊圖。
        ///
        /// ⚠️ garden8 的規格（別的程式依賴）：
        ///    * soil-dry / soil-wet：88×62，頂面菱形剛好 88×44（等距格子一格）、下面 9px 側面，上下對稱留邊 →
        ///      圖片正中心＝頂面中心，置中樞紐、縮放 1 直接放在花圃座標上。
        ///    * 花：234×96，6 欄 × 2 列（排法同舊圖），每格 39×48 原生像素，遊戲裡跟女巫一樣 ×1.6
        ///      （像素大小跟她一致）；莖的入土點在每格水平正中、底邊往上 <see cref="PixelFlowerFootPadPx"/>，
        ///      所有階段同一列 → 換階段不會跳。
        ///    縮放與位移看 <see cref="PixelSoil"/>／<see cref="PixelFlowers"/>（GardenData.PlotScale 等）。
        /// ⚠️ 背包裡花的圖示還是 items8（TryPixelItem 蓋過走圖那格），跟這個開關無關。
        /// </summary>
        public static readonly bool UsePixelPlants = true;

        /// <summary>新花圖：莖的入土點到格子底邊的距離（px、縮放前）。</summary>
        public const float PixelFlowerFootPadPx = 3f;

        static bool pixelSoil, pixelFlowers;

        /// <summary>土壤磚實際載到的是 garden8 新圖。</summary>
        public static bool PixelSoil => pixelSoil;

        /// <summary>
        /// 花的走圖實際載到的是 garden8 新圖。
        /// ⚠️ 三種花共用一個旗標（GardenData.FlowerScale 不分花）：garden8 只缺其中一種的話那種會用錯縮放 ——
        ///    --restore 是整個資料夾一起刪，正常不會發生。
        /// </summary>
        public static bool PixelFlowers => pixelFlowers;

        // ──────────── 女巫圖集（witch8）────────────
        //
        // Resources/witch8/<造型>.png 的排法（由原專案 tools/export_witch8.py 產生）：
        //   列 0       站姿，欄＝方向
        //   列 1..8    走路，列 1+d ＝方向 d，欄＝動畫幀
        //   列 9..16   跑步，列 9+d ＝方向 d，欄＝動畫幀
        //   列 17..24  施法，列 17+d ＝方向 d，欄＝動畫幀（6 幀）
        //
        // ⚠️ 施法那組是所有「動作」共用的：施法、澆水、採集、摘花、種花。
        //    新角色沒有蹲下的圖，所以圖集裡不再有前一位紫袍女巫的任何一格。
        //    之後真的做了蹲下的八方向圖，再加一段列並讓 gather/pick 改讀那組即可。

        const int W8Cols = 8, W8Rows = 25;
        const int W8RowWalk = 1, W8RowRun = 9, W8RowCast = 17;
        const int W8CastFrames = 6;

        public const int WitchDirs = 8;

        /// <summary>
        /// 女巫節點的縮放。**照星露谷的人物比例定** —— 星露谷 1280×720 一格 64px，
        /// 農夫可見身高約 112px ＝畫面高的 15.5%；我們的設計解析度是 960×640，
        /// 所以要 640×0.155 ≈ 99px，66 × 1.6 = 106（可見 93px，14.5%）剛好落在那個帶上。
        /// 1:1 畫的話只有畫面高的 10%，比星露谷小了一號。
        /// 村民要一起改（見 VillagerAnim.Scale）—— 但**不是跟著等比放大**，兩邊原圖的
        /// 格子高不一樣（女巫 66px、村民 100px），要各自量可見高度來對。
        /// </summary>
        public const float WitchScale = 1.6f;

        // ──────────── 道具圖示（8-bit 像素風）────────────

        /// <summary>
        /// 開關：true ＝ 道具圖示改用 tools/gen_item_art.py 程式點陣畫的 8-bit 圖（Resources/items8/）；
        /// false ＝ 退回原本那批尺寸不一的厚塗圖（items/、potions/、candy/item-*、garden/*-seed、花的走圖切格）。
        /// 舊圖一張都沒刪，改這裡就好。
        ///
        /// ⚠️ items8 的規格（別的程式依賴）：每張都是 **96×96**（邏輯 24×24 × 4）、圖案水平置中、
        ///    **底部貼齊**（最底下留 1 個邏輯格）、四周至少留 1 格透明。
        ///    → UI 的方框直接撐滿也不會變形；貨架把它等比縮到約 24px 高，每件都「坐」在同一條線上；
        ///    → 世界裡照原尺寸畫的地方（採集飄字、顧客泡泡、澆水的水滴）要用 <see cref="ItemIconWorld"/>
        ///      換算縮放，不能再假設「最長邊＝內容大小」—— 圖案只佔 96 裡的約 80%。
        /// ⚠️ 開著開關但 items8 裡缺某張（例如跑過 gen_item_art.py --restore），那件會自動退回舊圖，不會變成沒圖示。
        /// </summary>
        public static readonly bool UsePixelItems = true;

        /// <summary>
        /// 世界空間（PPU＝1）裡顯示一個道具圖示時，整張圖的邊長要縮到幾 px。傳入「舊圖時代」用的值。
        /// 舊圖的內容幾乎貼滿整張圖，所以原本「最長邊縮到 34px」＝東西本身約 34px；
        /// 8-bit 圖的內容約佔 96 的 20/24，要 40px 才看起來一樣大（40 × 20/24 ≈ 33）。
        /// </summary>
        public static float ItemIconWorld(float legacyPx) => UsePixelItems ? legacyPx * 40f / 34f : legacyPx;

        // ──────────── 路人走路圖（8-bit 像素風）────────────

        /// <summary>
        /// 開關：true ＝ 村民／顧客改用 tools/gen_villager_art.py 程式點陣畫的走路圖（Resources/villagers8/）；
        /// false ＝ 退回原本那批 AI 厚塗圖（Resources/villagers/，一張都沒刪）。
        /// 開著但 villagers8 裡缺某位（例如跑過 gen_villager_art.py --restore），那位自動退回舊圖。
        ///
        /// ⚠️ villagers8 的規格（別的程式依賴）：每張 **224×216**、4 欄 × 3 列、每格 **56×72**
        ///    （原生 1px 像素，不放大 —— 跟女巫 witch8 一樣）；角色水平置中；**鞋底在格子底邊往上 3px**，
        ///    11 位、所有幀都一樣 —— 所以不同人的縮放與腳底偏移只看「新圖或舊圖」，見
        ///    <see cref="VillagerArtScale"/>、<see cref="VillagerFootPad"/>。
        ///    （2026-11-27 第二版；第一版是 28×36 邏輯格 ×3 的 336×324 粗像素圖，已被覆蓋。）
        /// </summary>
        public static readonly bool UsePixelVillagers = true;

        // ──────────── 家具／裝飾（細畫版）────────────

        /// <summary>
        /// 開關：true ＝ 家具與裝飾先讀 tools/gen_furniture8.py 畫的細畫版（Resources/furniture8/、decor8/，
        /// 跟魔女房間 brew8 同一套畫法），缺哪張就退回舊資料夾那張（furniture/ 的 ×3 粗像素、decor/ 的厚塗）。
        /// false ＝ 全部舊圖（2026-11-28 新加的陳列桌、燈、家具、地毯沒有舊圖 → 花店不列、店裡不畫）。
        /// ⚠️ 陳列位／實心範圍／光暈點跟著圖走：細畫版在 Data/FurnitureArt8.cs、舊圖在 ShopDisplaySlots／FurnitureBounds，
        ///    兩邊都用「載到的圖尺寸」認，所以逐張混用也不會擺錯位子。
        /// ⚠️ 細畫版裝飾直接畫在遊戲尺度上（縮放 1）；舊裝飾照 DecorDef.Scale —— 一律經 <see cref="DecorScale"/>。
        /// </summary>
        public static readonly bool UsePixelFurniture = true;

        /// <summary>
        /// 新走路圖在 <see cref="VillagerAnim.Scale"/> 之上**再乘**的倍數（舊圖是 1）。
        /// ＝ <see cref="WitchScale"/>：新圖跟女巫一樣是原生 1px 像素，乘同一個倍數**像素才一樣大**（不是量身高湊出來的）。
        /// 畫面上的可見高（原生 px ×1.6）：主角女巫 58 → 93px；小魔女含帽 59 → 94、騎掃帚 58 → 93、法師含法杖 61 → 98、
        /// 旅人 48 → 77（沒戴帽）；兔子／兔子魔女含耳朵 54／53 → 86／85、小鹿含角 52 → 83、狐狸含耳朵 49 → 78、
        /// 妖精含蘑菇帽 46 → 74、青蛙含釣竿 44 → 70、刺蝟 41 → 66。
        /// ⚠️ 改女巫的 WitchScale 時這裡會一起變（村民跟著女巫走，像素保持一樣大）；
        ///    tools/gen_villager_art.py 的 GAME_SCALE（實景合成預覽用）要手動跟著改。
        /// </summary>
        public const float PixelVillagerScale = WitchScale;

        /// <summary>新走路圖：鞋底到格子底邊的距離（原生 px、縮放前；同女巫的 CharacterAnimator.FootPad）。舊圖沒有統一的基準線，當 0。</summary>
        const float PixelVillagerFootPadPx = 3f;

        /// <summary>實際載到 villagers8 新圖的村民（其餘是舊圖）。</summary>
        static readonly HashSet<string> pixelVillagers = new();

        /// <summary>這位村民的圖要在 VillagerAnim 的縮放之上再乘多少（新圖 <see cref="PixelVillagerScale"/>、舊圖 1）。</summary>
        public static float VillagerArtScale(string name) => pixelVillagers.Contains(name) ? PixelVillagerScale : 1f;

        /// <summary>鞋底在格子底邊往上幾 px（縮放前）—— 影子要對準鞋底用（同女巫的 CharacterAnimator.FootPad）。</summary>
        public static float VillagerFootPad(string name) => pixelVillagers.Contains(name) ? PixelVillagerFootPadPx : 0f;

        /// <summary>
        /// 影子寬度要用格子寬的幾成。新圖格子 56px 寬、身體約佔 22～26，比女巫的格子（49）寬，
        /// 用 0.85 ≈ 49/56 → 影子跟女巫的一樣大；舊圖維持原本的整格（之前實機調過）。
        /// </summary>
        public static float VillagerShadowRatio(string name) => pixelVillagers.Contains(name) ? 0.85f : 1f;

        /// <summary>
        /// 這位村民是不是「一直在飄」（騎掃帚的魔女）：站著也要播走路表（上下浮、鬃毛擺），見 VillagerAnim.Update。
        /// 只有新圖這樣畫；舊圖的 broomwitch 第 0 欄是站姿，維持站著不動。
        /// </summary>
        public static bool VillagerHovers(string name) => name == "broomwitch" && pixelVillagers.Contains(name);

        // ──────────── 快取 ────────────

        static readonly Dictionary<string, Sprite> items = new();         // 材料/藥水名 → 圖
        static readonly Dictionary<string, Sprite[][]> villagers = new(); // 村民名 → [面向][幀]
        static readonly Dictionary<string, Sprite[]> emotes = new();      // 表情名 → 動畫幀
        static readonly Dictionary<string, Sprite> portraits = new();
        static readonly Dictionary<string, Sprite> decor = new();
        static readonly Dictionary<string, Sprite> clockParts = new();
        static readonly Dictionary<string, Sprite> seasonIcons = new();
        static readonly Dictionary<string, Sprite> soil = new();
        static readonly Dictionary<string, Sprite[][]> flowers = new();   // 花名 → [健康/枯萎][階段]
        static readonly Dictionary<string, Sprite> candyArt = new();
        static readonly Dictionary<string, Sprite> furnitureArt = new();
        /// <summary>試載過的家具／裝飾（"f:id"／"d:id"）—— 缺圖的也記，FurnitureArt() 才不會每次都去 Resources 找。</summary>
        static readonly HashSet<string> furnTried = new();
        /// <summary>實際載到細畫版（decor8）的裝飾：顯示縮放用 1，見 DecorScale。</summary>
        static readonly HashSet<string> pixelDecor = new();

        static readonly Sprite[] cauldron = new Sprite[CauldronFrameCount];
        static readonly Sprite[] gather = new Sprite[GatherFrameCount];
        static readonly Sprite[] water = new Sprite[WaterFrameCount];
        static readonly Sprite[] pick = new Sprite[PickFrameCount];

        static Sprite[] w8Idle = Array.Empty<Sprite>();
        static Sprite[][] w8Walk = Array.Empty<Sprite[]>();
        static Sprite[][] w8Run = Array.Empty<Sprite[]>();
        static Sprite[][] w8Cast = Array.Empty<Sprite[]>();
        static Sprite w8Sleep;

        static Sprite castFrame, sleepingFrame;          // 舊手繪女巫的墊底圖
        static Sprite dialogueBoxFrame, questScrollFrame, updateFrameArt;
        static Sprite brewRoomDayFrame, brewRoomNightFrame, gardenFrame, shopRoomFrame;
        /// <summary>SVG 重畫的魔女房間（Resources/rooms/brew/）：Resources 路徑 → Sprite（樞紐照配置表放在落腳點）。</summary>
        static readonly Dictionary<string, Sprite> brewArt = new();
        static Sprite brewGlowSprite;

        static string outfitId = "";                     // ""＝預設造型
        static readonly HashSet<string> requested = new();
        static bool started;

        // ──────────── 載入工具 ────────────

        static Texture2D Tex(string path)
        {
            var t = Resources.Load<Texture2D>(path);
            if (t == null) Debug.LogWarning($"[GameArt] 載入失敗 {path}");
            return t;
        }

        static void LoadImg(Dictionary<string, Sprite> map, string key, string path)
        {
            var t = Tex(path);
            if (t != null) map[key] = SheetSlicer.Whole(t);
        }

        /// <summary>
        /// 載入一個道具圖示：開關開著且 items8/&lt;file&gt; 存在就用 8-bit 圖，否則走舊路徑。
        /// </summary>
        static void LoadItemIcon(string key, string legacyPath, string file)
        {
            if (TryPixelItem(key, file)) return;
            LoadImg(items, key, legacyPath);
        }

        /// <summary>
        /// 只試 items8；成功就登記進 items 並回 true。
        /// ⚠️ 直接用 Resources.Load、不經 Tex() —— 缺圖時退回舊圖是預期中的情況，不該噴警告。
        /// </summary>
        static bool TryPixelItem(string key, string file)
        {
            if (!UsePixelItems) return false;
            var t = Resources.Load<Texture2D>($"items8/{file}");
            if (t == null) return false;
            items[key] = SheetSlicer.Whole(t);
            return true;
        }

        /// <summary>
        /// 載入一件家具／裝飾的圖：開關開著先試細畫版（furniture8／decor8），沒有再退回舊資料夾（furniture／decor）。
        /// 舊資料夾也沒有（例如 2026-11-28 才加的燈、陳列桌）＝這件沒有圖（花店不會列、店裡不會畫）。
        /// ⚠️ 直接 Resources.Load、不經 Tex()：缺圖是預期中的，不噴警告。試過一次就記下來，不會每幀重試。
        /// </summary>
        static Sprite LoadFurnishing(string id, bool isDecor)
        {
            furnTried.Add((isDecor ? "d:" : "f:") + id);
            string newDir = isDecor ? "decor8" : "furniture8", oldDir = isDecor ? "decor" : "furniture";
            var t = UsePixelFurniture ? Resources.Load<Texture2D>($"{newDir}/{id}") : null;
            bool pixel = t != null;
            if (t == null) t = Resources.Load<Texture2D>($"{oldDir}/{id}");
            if (t == null) return null;
            var sp = SheetSlicer.Whole(t);
            if (isDecor)
            {
                decor[id] = sp;
                if (pixel) pixelDecor.Add(id); else pixelDecor.Remove(id);
            }
            else furnitureArt[id] = sp;
            return sp;
        }

        static Sprite LoadSingle(string path, Vector2? pivot = null)
        {
            var t = Tex(path);
            return t != null ? SheetSlicer.Whole(t, pivot) : null;
        }

        static void LoadIndexed(Sprite[] arr, int i, string path, Vector2? pivot = null)
        {
            var t = Tex(path);
            if (t != null) arr[i] = SheetSlicer.Whole(t, pivot);
        }

        /// <summary>載入表情 strip，切成每幀一個 Sprite。</summary>
        static void LoadEmote(string name)
        {
            var info = EmoteInfo[name];
            var t = Tex($"emotes/{name}");
            if (t == null) return;
            var arr = new Sprite[info.N];
            for (int i = 0; i < info.N; i++) arr[i] = SheetSlicer.StripCell(t, i, info.W, info.H);
            emotes[name] = arr;
        }

        /// <summary>
        /// 載入女巫圖集，依 W8_* 的排法切成站姿/走路/跑步/施法。
        /// </summary>
        /// <param name="id">造型 id（""＝預設那張 base.png）</param>
        static void LoadWitch8(string id)
        {
            string file = string.IsNullOrEmpty(id) ? "base" : id;
            var t = Tex($"witch8/{file}");
            if (t != null)
            {
                var idle = new Sprite[WitchDirs];
                var walk = new Sprite[WitchDirs][];
                var run = new Sprite[WitchDirs][];
                var cast = new Sprite[WitchDirs][];
                for (int d = 0; d < WitchDirs; d++)
                {
                    // ⚠️ 樞紐一律用 SheetSlicer.Foot（格子底邊）—— 女巫的 SpriteRenderer
                    //    就掛在 Player 本身，沒有「圖往上推半身高」的子物件，所以要靠樞紐
                    //    讓 position ＝ 落腳點，才跟村民/家具/搬過來的座標同一套。
                    idle[d] = SheetSlicer.Cell(t, d, 0, W8Cols, W8Rows, SheetSlicer.Foot);
                    walk[d] = SheetSlicer.Row(t, W8RowWalk + d, W8Cols, W8Rows, SheetSlicer.Foot);
                    run[d] = SheetSlicer.Row(t, W8RowRun + d, W8Cols, W8Rows, SheetSlicer.Foot);
                    var ca = new Sprite[W8CastFrames];
                    for (int c = 0; c < W8CastFrames; c++)
                        ca[c] = SheetSlicer.Cell(t, c, W8RowCast + d, W8Cols, W8Rows, SheetSlicer.Foot);
                    cast[d] = ca;
                }
                w8Idle = idle; w8Walk = walk; w8Run = run; w8Cast = cast;
            }
            // 睡覺立繪是另一張（含床，裁切框跟角色不一樣）
            w8Sleep = LoadSingle(string.IsNullOrEmpty(id) ? "witch8/sleep" : $"witch8/{id}-sleep");
        }

        /// <summary>
        /// 載入一位村民的走路表，切成 [列][欄]（列＝面向，欄＝動畫幀）。
        /// 開關開著且 villagers8/&lt;name&gt; 存在就用 8-bit 新圖（見 <see cref="UsePixelVillagers"/>），否則舊圖。
        /// 兩種圖的排法一樣（4 欄 × 3 列、下／側〔朝左〕／上），只有格子大小與基準線不同。
        /// </summary>
        static void LoadVillager(string name)
        {
            // ⚠️ 新圖直接 Resources.Load、不經 Tex() —— 缺圖時退回舊圖是預期中的情況，不該噴警告
            var t = UsePixelVillagers ? Resources.Load<Texture2D>($"villagers8/{name}") : null;
            if (t != null) pixelVillagers.Add(name);
            else
            {
                pixelVillagers.Remove(name);
                t = Tex($"villagers/{name}");
            }
            if (t == null) return;
            var rows = new Sprite[VillagerRows][];
            for (int r = 0; r < VillagerRows; r++)
                rows[r] = SheetSlicer.Row(t, r, VillagerCols, VillagerRows);
            villagers[name] = rows;
        }

        /// <summary>
        /// 載入一種花的走圖，切成 [列][階段]（列 0 健康、列 1 枯萎）。
        /// 順便把「開花那一格」登記成該花的道具圖示，背包/貨架/顧客就都有圖可用。
        /// </summary>
        static void LoadFlower(string art, string flowerName)
        {
            // 8-bit 新圖優先（見 UsePixelPlants）；直接 Resources.Load —— 缺圖退回舊圖是預期中的，不噴警告
            var t = UsePixelPlants ? Resources.Load<Texture2D>($"garden8/{art}") : null;
            if (t != null) pixelFlowers = true;
            else t = Tex($"garden/{art}");
            if (t == null) return;
            var rows = new Sprite[FlowerRows][];
            for (int r = 0; r < FlowerRows; r++)
                rows[r] = SheetSlicer.Row(t, r, FlowerCols, FlowerRows);
            flowers[art] = rows;
            items[flowerName] = rows[0][FlowerCols - 2];   // 盛開那一格＝道具圖示
        }

        // ──────────── 分區載入 ────────────

        /// <summary>場景名 → 除了 common 之外還要載入的區域組。</summary>
        static readonly Dictionary<string, string[]> SceneGroups = new()
        {
            ["main"] = Array.Empty<string>(),                          // 森林：只需 common
            ["town"] = new[] { "portraits", "decor", "villagers" },     // 城鎮
            ["shop"] = new[] { "shop", "decor", "villagers" },          // 自己的店
            ["brew"] = new[] { "brew" },                                // 藥水室
            ["garden"] = new[] { "garden", "villagers" },               // 後花園
            ["candy"] = new[] { "candy" },                              // 糖果鎮
        };

        /// <summary>保險用：全部區域組（拿不到場景名時退回全載）。</summary>
        static readonly string[] AllAreaGroups =
            { "portraits", "decor", "shop", "villagers", "garden", "brew", "candy" };

        /// <summary>載入一個區域組（idempotent —— 已請求過就跳過）。</summary>
        static void LoadGroup(string name)
        {
            if (!requested.Add(name)) return;

            switch (name)
            {
                case "common":
                    // 道具圖示：items8 跟舊圖用**同一個檔名**（見 UsePixelItems），只換資料夾
                    foreach (var kv in Items.ItemFiles) LoadItemIcon(kv.Key, $"items/{kv.Value}", kv.Value);
                    foreach (var kv in Items.PotionItems) LoadItemIcon(kv.Key, $"potions/{kv.Value}", kv.Value);
                    // 糖果鎮進的貨也要在背包/貨架/顧客那邊看得到圖 → 放 common
                    foreach (var kv in Items.CandyItems) LoadItemIcon(kv.Key, $"candy/{kv.Value}", kv.Value);
                    // 花圃澆水的水花（GardenPlot.PlayWater 用 Item("水滴")）：舊版沒有這張圖、一直退回程式生成的小白點
                    TryPixelItem("水滴", "water-drop");
                    foreach (var f in ClockFiles) LoadImg(clockParts, f, $"ui/clock/{f}");
                    foreach (var f in SeasonFiles) LoadImg(seasonIcons, f, $"ui/season/{f}");
                    dialogueBoxFrame = LoadSingle("ui/dialogue-box");
                    questScrollFrame = LoadSingle("ui/quest-scroll");
                    updateFrameArt = LoadSingle("ui/update-frame");
                    LoadWitch8(outfitId);
                    // 舊手繪女巫的施法/睡覺姿勢：只在圖集載不到時墊底
                    // 這幾張也是直接貼到 Player 的 SpriteRenderer 上 → 跟圖集一樣要腳底樞紐，
                    // 不然墊底的時候女巫會整個往上跳半身高。
                    // （sleepingFrame 例外：那是 SleepOverlay 的立繪，不掛在 Player 上）
                    castFrame = LoadSingle("witch/cast", SheetSlicer.Foot);
                    sleepingFrame = LoadSingle("witch/sleeping");
                    for (int i = 0; i < GatherFrameCount; i++)
                        LoadIndexed(gather, i, $"witch/gather{i + 1}", SheetSlicer.Foot);
                    // 花與種子的圖示要在每個場景都拿得到（背包、貨架、顧客想要的東西都會用到），
                    // 所以放 common；只有後花園會用到的土壤磚與澆水姿勢才留在 garden 組。
                    foreach (var f in GardenData.Flowers)
                    {
                        LoadFlower(f.Art, f.Flower);
                        // 花的收成圖示：LoadFlower 先登記走圖「盛開那一格」，有 8-bit 圖就蓋過去。
                        // ⚠️ 這裡只換道具圖示；花圃上的成長走圖（flowers[]）與土壤磚走 UsePixelPlants（garden8）。
                        TryPixelItem(f.Flower, f.Art);
                        LoadItemIcon(f.Seed, $"garden/{f.Art}-seed", $"{f.Art}-seed");
                    }
                    break;

                case "portraits":
                    foreach (var f in PortraitFiles) LoadImg(portraits, f, $"portraits/{f}");
                    break;

                case "decor":
                    // 細畫版（furniture8／decor8）優先、逐張退回舊圖，見 UsePixelFurniture。
                    // 家具跟裝飾同一組：花店（城鎮）要畫得出家具圖示，店裡要擺出來，兩邊都載得到。
                    // 別的場景（例如家裡）沒載這組也沒關係：FurnitureArt()／Decoration() 查不到會當場補載那一張。
                    foreach (var d in Decor.Catalog) LoadFurnishing(d.Id, true);
                    foreach (var f in Furniture.All) LoadFurnishing(f.Id, false);
                    break;

                case "shop":
                    foreach (var k in EmoteInfo.Keys) LoadEmote(k);
                    shopRoomFrame = LoadSingle("rooms/shop-room");
                    break;

                case "villagers":
                    foreach (var f in VillagerFiles) LoadVillager(f);
                    break;

                case "garden":
                    foreach (var f in SoilFiles)
                    {
                        // 8-bit 新圖優先（見 UsePixelPlants），缺圖退回舊圖
                        var st = UsePixelPlants ? Resources.Load<Texture2D>($"garden8/{f}") : null;
                        if (st != null) { soil[f] = SheetSlicer.Whole(st); pixelSoil = true; }
                        else LoadImg(soil, f, $"garden/{f}");
                    }
                    // 同上：貼到 Player 上的動作圖 → 腳底樞紐
                    for (int i = 0; i < WaterFrameCount; i++)
                        LoadIndexed(water, i, $"witch/water{i + 1}", SheetSlicer.Foot);
                    for (int i = 0; i < PickFrameCount; i++)
                        LoadIndexed(pick, i, $"witch/pick{i + 1}", SheetSlicer.Foot);
                    gardenFrame = LoadSingle("rooms/garden");
                    break;

                case "candy":
                    // ⚠️ 地圖與房子/裝飾在 Cocos 版是場景節點（圖在 assets/art/candy，場景用 uuid 參照），
                    //    所以原本這裡不載。Unity 這邊 art/ 也搬進了 Resources，之後 CandyTown 可以直接載；
                    //    先維持原行為，只載執行期才生成的 NPC 與路人。
                    foreach (var c in Candy.Critters) LoadImg(candyArt, c.Art, $"candy/{c.Art}");
                    break;

                case "brew":
                    if (Core.BrewRoom.UseSvgRoom) LoadBrewRoom();
                    else
                    {
                        // 舊房間（整張背景圖＋舊鍋爐）：BrewRoom.UseSvgRoom = false 時才用
                        for (int i = 0; i < CauldronFrameCount; i++) LoadIndexed(cauldron, i, $"cauldron/f{i}");
                        brewRoomDayFrame = LoadSingle("rooms/brew-room-day");
                        brewRoomNightFrame = LoadSingle("rooms/brew-room-night");
                    }
                    // 造型立繪只有房間裡的衣櫃會用到，所以掛在 brew 組，不佔 common
                    // （資料表叫 OutfitCatalog 而不是 Outfits —— Core 命名空間裡有一個
                    //   同名的 Outfits 管「現在穿哪一套」，撞名時錯誤訊息完全看不出原因）
                    foreach (var o in OutfitCatalog.All)
                        if (!string.IsNullOrEmpty(o.Portrait))
                            LoadImg(portraits, o.Portrait, $"portraits/{o.Portrait}");
                    break;
            }
        }

        /// <summary>
        /// 載入 SVG 重畫的魔女房間：房間殼（日／夜）、每件家具的每一幀、光暈。
        /// 家具的樞紐照 Data.BrewRoomLayout 的 PivotX/PivotY（像素）放在落腳點 —— 物件的 position 直接擺落腳點。
        /// 同一張圖給好幾件用（蠟燭）時樞紐一樣（同尺寸的落地範圍），載一次就好。
        /// </summary>
        static void LoadBrewRoom()
        {
            var day = BrewTex(BrewRoomLayout.ShellDay);
            var night = BrewTex(BrewRoomLayout.ShellNight);
            brewRoomDayFrame = day != null ? SheetSlicer.Whole(day) : null;
            brewRoomNightFrame = night != null ? SheetSlicer.Whole(night) : null;
            foreach (var p in BrewRoomLayout.Pieces)
                foreach (var path in p.Frames)
                {
                    if (brewArt.ContainsKey(path)) continue;
                    var t = BrewTex(path);
                    if (t == null) continue;
                    brewArt[path] = SheetSlicer.Whole(t, new Vector2(p.PivotX / t.width, p.PivotY / t.height));
                }
            var g = BrewTex(BrewRoomLayout.Glow);
            if (g != null)
            {
                // 光暈是唯一的漸層圖：放大貼的時候要平滑，不能用像素風的 Point
                g.filterMode = FilterMode.Bilinear;
                brewGlowSprite = SheetSlicer.Whole(g);
            }
        }

        /// <summary>
        /// 魔女房間的一張圖：Core.BrewRoom.UsePixelRoom 開著時先讀細畫版 rooms/brew8/（同檔名、同尺寸、同樞紐，
        /// tools/gen_brew_room8.py 產生），缺圖才逐張退回 rooms/brew/。配置表裡的路徑仍是 rooms/brew/…（樞紐照表算）。
        /// </summary>
        static Texture2D BrewTex(string path)
        {
            const string Old = "rooms/brew/";
            if (Core.BrewRoom.UsePixelRoom && path.StartsWith(Old, System.StringComparison.Ordinal))
            {
                var t = Resources.Load<Texture2D>("rooms/brew8/" + path.Substring(Old.Length));
                if (t != null) return t;
            }
            return Tex(path);
        }

        // ──────────── 對外 API（跟 Cocos 版一致，呼叫端不用改）────────────

        /// <summary>
        /// 目前已請求的所有組是否都載入完成。
        /// Unity 的 Resources.Load 是同步的，所以 Preload() 一回來就是好了。
        /// </summary>
        public static bool Ready => started;

        /// <summary>
        /// 開始預載（重複呼叫安全）。載入 common ＋該場景的區域組。
        /// 換場景後各元件於 Awake 再呼叫一次，就會補載新場景需要的組。
        /// ⚠️ 未知場景 → 退回全部載入（等同原專案行為，寧可不省也不缺圖）。
        /// </summary>
        public static void Preload(string sceneName = null)
        {
            started = true;
            LoadGroup("common");
            sceneName ??= SceneManager.GetActiveScene().name;
            var groups = SceneGroups.TryGetValue(sceneName, out var g) ? g : AllAreaGroups;
            foreach (var n in groups) LoadGroup(n);
        }

        /// <summary>載入完成的回呼。同步載入下就是立刻執行（API 保留，呼叫端不用改）。</summary>
        public static void OnReady(Action cb)
        {
            if (!started) Preload();
            cb?.Invoke();
        }

        /// <summary>
        /// 換上某套造型的圖：id ＝ Resources/witch8/&lt;id&gt;.png，空字串＝回到預設那批。
        /// 同步載入，所以沒有 Cocos 版那個「晚到的回呼蓋掉新造型」的競態要擋。
        /// </summary>
        public static void ApplyOutfit(string id)
        {
            if (id == outfitId) return;
            outfitId = id;
            started = true;
            LoadWitch8(id);          // 造型＝同一張圖集的改色版，整張換掉
        }

        /// <summary>女巫圖集載好了沒（沒好的話 CharacterAnimator 會先用場景指定的舊圖）。</summary>
        public static bool WitchReady() => w8Idle.Length > 0;

        static int WrapDir(int dir) => ((dir % WitchDirs) + WitchDirs) % WitchDirs;

        /// <summary>某個方向的站姿（dir 見 WitchDir；未載入回 null）。</summary>
        public static Sprite WitchIdle(int dir) =>
            w8Idle.Length > 0 ? w8Idle[WrapDir(dir)] : null;

        /// <summary>某個方向的走路幀（未載入回空陣列）。</summary>
        public static Sprite[] WitchWalk(int dir) =>
            w8Walk.Length > 0 ? w8Walk[WrapDir(dir)] : Array.Empty<Sprite>();

        /// <summary>某個方向的跑步幀（衝刺用；未載入回空陣列 → 呼叫端自己退回走路）。</summary>
        public static Sprite[] WitchRun(int dir) =>
            w8Run.Length > 0 ? w8Run[WrapDir(dir)] : Array.Empty<Sprite>();

        /// <summary>
        /// 某個方向的動作動畫幀（8 方向各 6 幀）。
        /// **施法／澆水／採集／摘花／種花共用**這一組 —— 新角色只做了這一段動作動畫。
        /// </summary>
        public static Sprite[] ActionFrames(int dir = WitchDir.South) =>
            w8Cast.Length > 0 ? w8Cast[WrapDir(dir)] : Array.Empty<Sprite>();

        /// <summary>某個方向的施法幀（沒有圖集時退回舊的單張姿勢）。</summary>
        public static Sprite[] CastFrames(int dir = WitchDir.South)
        {
            var v = ActionFrames(dir);
            if (v.Length > 0) return v;
            return castFrame != null ? new[] { castFrame } : Array.Empty<Sprite>();
        }

        static Sprite[] ActionOrLegacy(int dir, Sprite[] legacy)
        {
            var v = ActionFrames(dir);
            return v.Length > 0 ? v : legacy;
        }

        public static Sprite[] GatherFrames(int dir = WitchDir.South) => ActionOrLegacy(dir, gather);
        public static Sprite[] WaterFrames(int dir = WitchDir.South) => ActionOrLegacy(dir, water);
        public static Sprite[] PickFrames(int dir = WitchDir.South) => ActionOrLegacy(dir, pick);

        /// <summary>已載入的村民名字（TownFolk / CustomerManager 從這裡挑人）。</summary>
        public static string[] VillagerNames()
        {
            var outList = new List<string>(villagers.Count);
            foreach (var kv in villagers) outList.Add(kv.Key);
            return outList.ToArray();
        }

        /// <summary>某位村民某個面向的走路幀（面向見 VillagerDir）。</summary>
        public static Sprite[] VillagerFrames(string name, int dir) =>
            villagers.TryGetValue(name, out var rows) && dir >= 0 && dir < rows.Length
                ? rows[dir] : Array.Empty<Sprite>();

        public static Sprite Item(string name) => items.GetValueOrDefault(name);
        public static Sprite Portrait(string name) => portraits.GetValueOrDefault(name);
        /// <summary>裝飾的圖（沒載過會當場載；細畫版優先、退回舊圖；都沒有回 null）。</summary>
        public static Sprite Decoration(string id)
        {
            if (id == null) return null;
            if (!decor.TryGetValue(id, out var sp) && !furnTried.Contains("d:" + id)) sp = LoadFurnishing(id, true);
            return sp;
        }

        /// <summary>家具的圖（沒載過會當場載；細畫版優先、退回舊圖；都沒有回 null）。</summary>
        public static Sprite FurnitureArt(string id)
        {
            if (id == null) return null;
            if (!furnitureArt.TryGetValue(id, out var sp) && !furnTried.Contains("f:" + id)) sp = LoadFurnishing(id, false);
            return sp;
        }

        /// <summary>這件裝飾的顯示縮放：細畫版畫在遊戲尺度上（1）；舊圖用 DecorDef.Scale（0＝DecorCatalog.DefaultScale）。</summary>
        public static float DecorScale(string id)
        {
            if (Decoration(id) != null && pixelDecor.Contains(id)) return 1f;
            var d = Decor.ById(id);
            return d != null && d.Scale > 0f ? d.Scale : Core.DecorCatalog.DefaultScale;
        }

        /// <summary>任一件（家具或裝飾）的圖。</summary>
        public static Sprite FurnishingArt(string id) => Furniture.ById(id) != null ? FurnitureArt(id) : Decoration(id);
        public static Sprite CandyArt(string art) => candyArt.GetValueOrDefault(art);
        public static Sprite ClockPart(string name) => clockParts.GetValueOrDefault(name);
        public static Sprite[] Emote(string name) => emotes.GetValueOrDefault(name, Array.Empty<Sprite>());
        public static Sprite[] CauldronFrames() => cauldron;

        /// <summary>季節圖標（0 春 … 3 冬）。</summary>
        public static Sprite SeasonIcon(int season) =>
            season >= 0 && season < SeasonFiles.Length
                ? seasonIcons.GetValueOrDefault(SeasonFiles[season]) : null;

        /// <summary>土壤磚（乾/濕）。</summary>
        public static Sprite Soil(bool wet) => soil.GetValueOrDefault(wet ? "soil-wet" : "soil-dry");

        /// <summary>某種花在某個階段的圖（wilting＝走枯萎那一列）。</summary>
        public static Sprite Flower(string art, int stage, bool wilting)
        {
            if (!flowers.TryGetValue(art, out var rows)) return null;
            var row = rows[wilting ? 1 : 0];
            return stage >= 0 && stage < row.Length ? row[stage] : null;
        }

        public static Sprite WitchSleep => w8Sleep != null ? w8Sleep : sleepingFrame;
        public static Sprite DialogueBox => dialogueBoxFrame;
        public static Sprite QuestScroll => questScrollFrame;
        public static Sprite UpdateFrame => updateFrameArt;
        public static Sprite ShopRoom => shopRoomFrame;
        public static Sprite GardenRoom => gardenFrame;
        /// <summary>藥水室的背景：舊房間是整張圖，SVG 房間是「牆＋地板」的房間殼（日／夜）。</summary>
        public static Sprite BrewRoom(bool night) => night ? brewRoomNightFrame : brewRoomDayFrame;

        /// <summary>SVG 房間一件家具的所有幀（照 Frames 的順序；缺圖的位置是 null）。</summary>
        public static Sprite[] BrewFrames(in BrewPiece p)
        {
            var arr = new Sprite[p.Frames.Length];
            for (int i = 0; i < arr.Length; i++) arr[i] = brewArt.GetValueOrDefault(p.Frames[i]);
            return arr;
        }

        /// <summary>SVG 房間的夜晚光暈（白色＋alpha 的徑向漸層，顏色由 SpriteRenderer.color 給）。</summary>
        public static Sprite BrewGlow => brewGlowSprite;
    }
}
