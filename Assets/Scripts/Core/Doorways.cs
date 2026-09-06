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
        /// 城鎮小屋的門在整棟房子圖上的位置（物件原點在房子正中央底部）。
        /// 拱門偏左 —— 沒有這個位移，觸發點會落在房子正中間，看起來像從牆壁進去。
        /// </summary>
        static readonly Vector2 CottageDoor = new(-93f, 12f);

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
            AddShop("general-store", "按 E 收購材料",
                    () => UI.GeneralStorePanel.Ensure().Open());
            AddShop("flower-shop", "按 E 逛花店",
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

        static void AddShop(string nodeName, string hint, System.Action open)
        {
            var go = GameObject.Find(nodeName);
            if (go == null) { Debug.LogWarning($"[Doorways] 城鎮裡找不到 {nodeName}"); return; }
            if (go.GetComponent<ActionPoint>() != null) return;

            var a = go.AddComponent<ActionPoint>();
            a.hintText = hint;
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
