using UnityEngine;

namespace WitchShop.Data
{
    /// <summary>森林裡一個可採集的點（樹、灌木、藥草叢、落葉堆）。</summary>
    public class GatherSpot
    {
        public string Art;        // Resources 底下的圖路徑
        public float X, Y, Scale;
        public string Item;       // 產出什麼材料
        public float Range;       // 玩家離多近才採得到（像素）
        public float Cooldown;    // 採完幾秒後長回來
        public int MinYield, MaxYield;
        public string RareItem;   // 額外稀有掉落（空＝沒有）
        public float RareChance;
    }

    /// <summary>森林裡的純裝飾（不能採，只是擋著好看）。</summary>
    public class ForestProp { public string Art; public float X, Y, Scale; }

    /// <summary>
    /// 森林（原 main.scene）的擺設。
    ///
    /// ⚠️ 這個檔是**從 Cocos 的 main.scene 直接抽出來自動產生的**，不是手打的。
    ///    原本這 84 個採集點是在 Cocos 編輯器裡一個一個擺的，位置與每棵樹的產出設定
    ///    都存在場景檔的 JSON 裡。重擺一次不切實際，所以寫了個轉換器把座標與屬性
    ///    整批搬過來 —— 森林的地貌因此跟原版一模一樣。
    ///
    ///    要再跑一次轉換（例如原專案又加了樹），見 PortNotes.md 的「場景轉換」章節。
    /// </summary>
    public static class ForestLayout
    {
        /// <summary>地面草皮圖與整片大小（＝可走範圍）。</summary>
        public const string GroundArt = "art/ground-grass";
        public static readonly Vector2 GroundSize = new(2816f, 1792f);

        /// <summary>84 個採集點。</summary>
        public static readonly GatherSpot[] Spots =
        {
            new() { Art = "art/tree-apple-mature", X = 937.3f, Y = -131.7f, Scale = 0.482f, Item = "木材", Range = 150f, Cooldown = 8f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-mature", X = -283.8f, Y = -279.6f, Scale = 0.495f, Item = "木材", Range = 150f, Cooldown = 8f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-mature", X = -16.4f, Y = 490.0f, Scale = 0.493f, Item = "木材", Range = 150f, Cooldown = 8f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-mature", X = 190.8f, Y = 268.5f, Scale = 0.49f, Item = "木材", Range = 150f, Cooldown = 8f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-mature", X = -965.2f, Y = -559.1f, Scale = 0.507f, Item = "木材", Range = 150f, Cooldown = 8f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-mature", X = 487.6f, Y = 263.0f, Scale = 0.499f, Item = "木材", Range = 150f, Cooldown = 8f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-mature", X = -858.0f, Y = -255.8f, Scale = 0.508f, Item = "木材", Range = 150f, Cooldown = 8f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-mature", X = -499.0f, Y = -519.0f, Scale = 0.528f, Item = "木材", Range = 150f, Cooldown = 8f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-mature", X = 800.4f, Y = 349.2f, Scale = 0.518f, Item = "木材", Range = 150f, Cooldown = 8f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-mature", X = -861.0f, Y = 173.8f, Scale = 0.553f, Item = "木材", Range = 150f, Cooldown = 8f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-golden", X = -87.8f, Y = -431.7f, Scale = 0.493f, Item = "金蘋果", Range = 140f, Cooldown = 12f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-golden", X = 315.5f, Y = -135.5f, Scale = 0.532f, Item = "金蘋果", Range = 140f, Cooldown = 12f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-golden", X = 560.1f, Y = 45.8f, Scale = 0.485f, Item = "金蘋果", Range = 140f, Cooldown = 12f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-golden", X = -498.2f, Y = 457.2f, Scale = 0.512f, Item = "金蘋果", Range = 140f, Cooldown = 12f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-blossom", X = -1047.0f, Y = -787.2f, Scale = 0.462f, Item = "木材", Range = 140f, Cooldown = 8f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-blossom", X = 795.5f, Y = 777.5f, Scale = 0.5f, Item = "木材", Range = 140f, Cooldown = 8f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-blossom", X = -40.8f, Y = 730.8f, Scale = 0.478f, Item = "木材", Range = 140f, Cooldown = 8f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-blossom", X = 951.1f, Y = -760.3f, Scale = 0.533f, Item = "木材", Range = 140f, Cooldown = 8f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-blossom", X = 306.0f, Y = 645.7f, Scale = 0.539f, Item = "木材", Range = 140f, Cooldown = 8f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-blossom", X = -665.3f, Y = 749.1f, Scale = 0.468f, Item = "木材", Range = 140f, Cooldown = 8f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-blossom", X = 205.6f, Y = -579.9f, Scale = 0.466f, Item = "木材", Range = 140f, Cooldown = 8f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-sapling", X = -1150.4f, Y = -214.6f, Scale = 0.46f, Item = "樹枝", Range = 110f, Cooldown = 6f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-sapling", X = 677.1f, Y = 612.3f, Scale = 0.477f, Item = "樹枝", Range = 110f, Cooldown = 6f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-sapling", X = -894.6f, Y = 565.0f, Scale = 0.504f, Item = "樹枝", Range = 110f, Cooldown = 6f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-sapling", X = 1309.2f, Y = -163.9f, Scale = 0.535f, Item = "樹枝", Range = 110f, Cooldown = 6f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-sapling", X = -1194.5f, Y = -326.6f, Scale = 0.489f, Item = "樹枝", Range = 110f, Cooldown = 6f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-sapling", X = 1202.3f, Y = -125.7f, Scale = 0.537f, Item = "樹枝", Range = 110f, Cooldown = 6f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-sapling", X = 703.9f, Y = -418.5f, Scale = 0.463f, Item = "樹枝", Range = 110f, Cooldown = 6f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-sapling", X = -1245.6f, Y = 733.2f, Scale = 0.506f, Item = "樹枝", Range = 110f, Cooldown = 6f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-sapling", X = -970.3f, Y = 689.8f, Scale = 0.549f, Item = "樹枝", Range = 110f, Cooldown = 6f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-sapling", X = -760.3f, Y = -472.3f, Scale = 0.499f, Item = "樹枝", Range = 110f, Cooldown = 6f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-sapling", X = 477.7f, Y = 569.2f, Scale = 0.474f, Item = "樹枝", Range = 110f, Cooldown = 6f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-sapling", X = 1060.6f, Y = 402.4f, Scale = 0.518f, Item = "樹枝", Range = 110f, Cooldown = 6f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-sapling", X = -1204.9f, Y = -546.8f, Scale = 0.533f, Item = "樹枝", Range = 110f, Cooldown = 6f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/tree-apple-sapling", X = 585.5f, Y = -720.7f, Scale = 0.459f, Item = "樹枝", Range = 110f, Cooldown = 6f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-berry", X = 1106.4f, Y = -582.0f, Scale = 0.486f, Item = "漿果", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-berry", X = -363.7f, Y = 780.0f, Scale = 0.509f, Item = "漿果", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-berry", X = 639.9f, Y = -287.5f, Scale = 0.508f, Item = "漿果", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-berry", X = -1323.0f, Y = -257.0f, Scale = 0.485f, Item = "漿果", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-berry", X = -754.6f, Y = 566.2f, Scale = 0.532f, Item = "漿果", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-berry", X = 1021.3f, Y = 816.4f, Scale = 0.492f, Item = "漿果", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-berry", X = 859.4f, Y = -333.4f, Scale = 0.498f, Item = "漿果", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-berry", X = 985.6f, Y = -311.6f, Scale = 0.532f, Item = "漿果", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-berry", X = 936.1f, Y = 711.8f, Scale = 0.518f, Item = "漿果", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-berry", X = 490.4f, Y = -152.9f, Scale = 0.542f, Item = "漿果", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-berry", X = 1275.5f, Y = 517.2f, Scale = 0.486f, Item = "漿果", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-berry", X = 763.6f, Y = 525.3f, Scale = 0.527f, Item = "漿果", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-berry", X = -1268.5f, Y = 60.5f, Scale = 0.547f, Item = "漿果", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-berry", X = 1251.4f, Y = -382.1f, Scale = 0.514f, Item = "漿果", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-bramble", X = -364.7f, Y = 30.8f, Scale = 0.532f, Item = "黑莓", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-bramble", X = 673.9f, Y = -95.3f, Scale = 0.518f, Item = "黑莓", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-bramble", X = -1339.3f, Y = 361.6f, Scale = 0.454f, Item = "黑莓", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-bramble", X = -207.3f, Y = 823.7f, Scale = 0.475f, Item = "黑莓", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-bramble", X = -643.8f, Y = 45.2f, Scale = 0.519f, Item = "黑莓", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-bramble", X = -1138.7f, Y = -31.7f, Scale = 0.5f, Item = "黑莓", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-bramble", X = -1195.1f, Y = 336.0f, Scale = 0.465f, Item = "黑莓", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-bramble", X = -629.2f, Y = 595.4f, Scale = 0.454f, Item = "黑莓", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-bramble", X = -114.4f, Y = -698.6f, Scale = 0.52f, Item = "黑莓", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-bramble", X = 320.3f, Y = -714.6f, Scale = 0.515f, Item = "黑莓", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/bush-bramble", X = -1207.0f, Y = 554.8f, Scale = 0.538f, Item = "黑莓", Range = 110f, Cooldown = 5f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/leaf-pile", X = 578.9f, Y = -394.6f, Scale = 0.475f, Item = "落葉", Range = 100f, Cooldown = 3f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/leaf-pile", X = 1149.2f, Y = 319.7f, Scale = 0.536f, Item = "落葉", Range = 100f, Cooldown = 3f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/leaf-pile", X = -433.6f, Y = -836.5f, Scale = 0.52f, Item = "落葉", Range = 100f, Cooldown = 3f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/leaf-pile", X = -344.9f, Y = 622.3f, Scale = 0.472f, Item = "落葉", Range = 100f, Cooldown = 3f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/leaf-pile", X = -1313.4f, Y = -395.2f, Scale = 0.467f, Item = "落葉", Range = 100f, Cooldown = 3f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/leaf-pile", X = -1233.4f, Y = -761.0f, Scale = 0.457f, Item = "落葉", Range = 100f, Cooldown = 3f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/leaf-pile", X = -891.1f, Y = 378.9f, Scale = 0.529f, Item = "落葉", Range = 100f, Cooldown = 3f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/leaf-pile", X = 1152.0f, Y = -3.6f, Scale = 0.519f, Item = "落葉", Range = 100f, Cooldown = 3f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/leaf-pile", X = -1018.1f, Y = 493.5f, Scale = 0.513f, Item = "落葉", Range = 100f, Cooldown = 3f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/leaf-pile", X = 1189.5f, Y = -772.6f, Scale = 0.542f, Item = "落葉", Range = 100f, Cooldown = 3f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/herb-patch", X = -1323.4f, Y = -841.2f, Scale = 0.532f, Item = "藥草", Range = 100f, Cooldown = 4f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/herb-patch", X = -523.3f, Y = -107.6f, Scale = 0.532f, Item = "藥草", Range = 100f, Cooldown = 4f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/herb-patch", X = -701.5f, Y = -602.1f, Scale = 0.454f, Item = "藥草", Range = 100f, Cooldown = 4f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/herb-patch", X = 140.7f, Y = -740.3f, Scale = 0.465f, Item = "藥草", Range = 100f, Cooldown = 4f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/herb-patch", X = 169.7f, Y = -330.7f, Scale = 0.508f, Item = "藥草", Range = 100f, Cooldown = 4f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/herb-patch", X = 673.2f, Y = -813.7f, Scale = 0.454f, Item = "藥草", Range = 100f, Cooldown = 4f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/herb-patch", X = 909.3f, Y = 588.9f, Scale = 0.459f, Item = "藥草", Range = 100f, Cooldown = 4f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/herb-patch", X = -567.3f, Y = -284.2f, Scale = 0.532f, Item = "藥草", Range = 100f, Cooldown = 4f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/herb-patch", X = 970.1f, Y = 109.6f, Scale = 0.464f, Item = "藥草", Range = 100f, Cooldown = 4f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/herb-patch", X = -929.7f, Y = 14.8f, Scale = 0.527f, Item = "藥草", Range = 100f, Cooldown = 4f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/herb-patch", X = -948.9f, Y = 826.2f, Scale = 0.483f, Item = "藥草", Range = 100f, Cooldown = 4f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/herb-patch", X = 766.3f, Y = -574.4f, Scale = 0.546f, Item = "藥草", Range = 100f, Cooldown = 4f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/herb-patch", X = -732.3f, Y = 391.2f, Scale = 0.509f, Item = "藥草", Range = 100f, Cooldown = 4f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
            new() { Art = "art/herb-patch", X = -298.3f, Y = 433.4f, Scale = 0.546f, Item = "藥草", Range = 100f, Cooldown = 4f, MinYield = 1, MaxYield = 3, RareItem = "", RareChance = 0.15f },
        };

        /// <summary>9 個純裝飾。</summary>
        public static readonly ForestProp[] Props =
        {
            new() { Art = "art/bush-hedge", X = -242.8f, Y = -575.7f, Scale = 0.582f },
            new() { Art = "art/bush-hedge", X = -625.8f, Y = -717.9f, Scale = 0.544f },
            new() { Art = "art/bush-hedge", X = -612.8f, Y = 290.9f, Scale = 0.543f },
            new() { Art = "art/bush-hedge", X = 413.5f, Y = -373.7f, Scale = 0.537f },
            new() { Art = "art/bush-hedge", X = -1087.4f, Y = 215.8f, Scale = 0.527f },
            new() { Art = "art/bush-hedge", X = 1267.0f, Y = -619.0f, Scale = 0.527f },
            new() { Art = "art/bush-hedge", X = -1104.6f, Y = 657.1f, Scale = 0.598f },
            new() { Art = "art/bush-hedge", X = -277.1f, Y = 235.8f, Scale = 0.553f },
        };
    }
}
