using UnityEngine;
using WitchShop.Data;

namespace WitchShop.Core
{
    /// <summary>
    /// 執行期補上的門。
    ///
    /// 這些不直接存進場景檔 —— 原專案的理由是「Cocos 常常開著，改場景檔會被編輯器蓋掉」；
    /// 這裡沿用同樣的做法，好處是門的位置改了不用重建場景。
    ///
    /// 由 PlayerController 在對應場景呼叫 Install()。
    /// </summary>
    public static class Doorways
    {
        /// <summary>
        /// 城鎮小屋的門口觸發點，相對物件原點 —— ⚠️ 原點是**圖片中心**（城鎮物件的 position
        /// 都是圖片中心，不是房子底部）。cottage-home.png 是 290×258、scale 1：
        /// 正面左下的拱門約在圖上 x 63~103（中心約 83），門前的圓石階約 x 36~115、y 218~254。
        /// 觸發點放在石階正下方、圖片底緣往下 6px（圖上 (80, 264)）：
        ///   x：80 − 145 ＝ −65；y：129 − 264 ＝ −135。
        /// 建築的落地範圍底緣就是圖片底緣（世界 y 261），觸發點在它**外面**，
        /// 玩家從正面就走得到 70px 自動觸發圈，Obstacles 不必在牆上挖通道。
        /// （以前是 (−93, 12)，照「原點在底部」寫的，結果落在左牆半腰的屋簷上。）
        /// </summary>
        static readonly Vector2 CottageDoor = new(-65f, -135f);

        /// <summary>
        /// 開店／關店招牌（<see cref="ShopSignPost"/>）的落地點，同樣相對小屋的圖片中心。
        /// 圖上約 (159, 273)：正面右邊轉角的前方草地、石階右側，世界約 (−524, 246)（再對齊偶數像素）。
        /// ⚠️ 要在門口光圈（觸發點 (−65,−135) 為圓心的 76×30 橢圓）外面：x 至少離觸發點 76。
        /// tools/check_walkable.py 與 tools/gen_shop_sign.py 的預覽都讀這一行。
        /// </summary>
        static readonly Vector2 CottageSign = new(14f, -144f);

        /// <summary>在指定場景補上該有的門（重複呼叫安全）。</summary>
        public static void Install(string scene)
        {
            if (scene == "town") InstallTown();
            else if (scene == "shop") InstallShop();
        }

        static void InstallTown()
        {
            // 小屋＝自己的店的入口
            var cottage = GameObject.Find("cottage-home");
            if (cottage != null && cottage.GetComponent<SceneDoor>() == null)
            {
                var d = cottage.AddComponent<SceneDoor>();
                d.targetScene = "shop";
                d.hintText = "進入店裡";
                d.doorX = CottageDoor.x;
                d.doorY = CottageDoor.y;
            }
            // 店門口的開店／關店招牌＋風鈴（純顯示；開關店的入口在上方工具列 UI/CornerHud）。見 ShopSignPost 檔頭。
            if (cottage != null)
                ShopSignPost.Ensure((Vector2)cottage.transform.position + CottageSign);

            // ── 三位可以交談 / 發任務的 NPC ────────────────────────
            // ⚠️ NpcName 必須跟 Data.Quests 的 Giver、Data.Villagers 的 Name 一致，
            //    任務與友誼度都是用名字當 key 對應的。
            AddNpc("potion-shop", "地精老闆", "gnome", new[]
            {
                "喲，是新來的女巫吧？我是這間藥水鋪的地精，鎮上的老面孔了。",
                "你在森林採的材料，拿回自己的店裡上架，動物客人就會上門買。",
                "想賺得多，記得升級招牌招攬更多客人，貨架也要夠大才擺得下。",
                "祝你生意興隆，哈哈！",
            });
            AddNpc("scroll-shop", "精靈書商", "elf", new[] { "書店隨時歡迎你，慢慢逛。" });
            AddNpc("spell-shop", "魔法貓", "fox", new[] { "喵～今天也是好天氣呢。" });

            // ── 兩間可以買賣的商店 ────────────────────────────────
            // 頭上的提示是 [E][圖]（共用的 InteractHint）：雜貨鋪收購材料 → 金幣、花店 → 一朵花；文字只在開關關掉時用
            AddShop("general-store", "按 E 收購材料", HintIcons.Ui("act_sell"),
                    () => UI.GeneralStorePanel.Ensure().Open());
            AddShop("flower-shop", "按 E 逛花店", HintIcons.Items8("lavender"),
                    () => UI.FlowerShopPanel.Ensure().Open());
        }

        static void AddNpc(string nodeName, string npc, string portrait, string[] lines)
        {
            var go = GameObject.Find(nodeName);
            if (go == null) { Debug.LogWarning($"[Doorways] 城鎮裡找不到 {nodeName}"); return; }
            if (go.GetComponent<TalkNpc>() != null) return;

            var t = go.AddComponent<TalkNpc>();
            t.npcName = npc;
            t.portrait = portrait;
            t.lines = lines;
            t.interactRange = 220f;
        }

        static void AddShop(string nodeName, string hint, Sprite icon, System.Action open)
        {
            var go = GameObject.Find(nodeName);
            if (go == null) { Debug.LogWarning($"[Doorways] 城鎮裡找不到 {nodeName}"); return; }
            if (go.GetComponent<ActionPoint>() != null) return;

            var a = go.AddComponent<ActionPoint>();
            a.hintText = hint;
            a.hintSprite = icon;
            a.interactRange = 225f;
            a.onActivate = open;
        }

        static void InstallShop()
        {
            // 店裡的三個出口。等距房間沒辦法用「走出矩形邊界」那一套（地板是菱形，
            // 塞得進去的矩形只剩正中間一小塊），所以連「回城鎮」也做成地板上的門 ——
            // 三個出口規則一致，走上去就過圖。
            var doors = new (string Name, Cell Cell, string Target, string Hint)[]
            {
                ("TownDoor",   ShopRoom.DoorTown,   "town",   "回城鎮"),
                ("BrewDoor",   ShopRoom.DoorBrew,   "brew",   "進藥水室"),
                ("GardenDoor", ShopRoom.DoorGarden, "garden", "到後花園"),
            };

            foreach (var (name, cell, target, hint) in doors)
            {
                if (GameObject.Find(name) != null) continue;

                var p = ShopRoom.TileCenter(cell.gx, cell.gy);
                var go = new GameObject(name);
                go.transform.position = new Vector3(p.x, p.y, 0f);

                var d = go.AddComponent<SceneDoor>();
                d.targetScene = target;
                d.hintText = hint;
                // ⚠️ 提示範圍收到跟自動觸發一樣大。販售桌的櫃台也吃 E，
                //    兩個感應圈重疊的話「按 E 上架」會同時把人送去別的場景（原專案在花園那道門踩過）。
                d.interactRange = d.autoRange;
            }
        }
    }
}
