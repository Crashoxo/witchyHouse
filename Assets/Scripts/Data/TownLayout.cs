using UnityEngine;

namespace WitchShop.Data
{
    /// <summary>
    /// 城鎮（原 town.scene）的擺設。
    ///
    /// ⚠️ 跟 ForestLayout 一樣，是**從 Cocos 的 town.scene 自動抽出來的**，不是手打的。
    ///    含店家建築、灌木、路燈、圍籬、橋。座標已經把父層（Roads）的位移累加進去，
    ///    所以全部都是世界座標，直接擺就對位。
    /// </summary>
    public static class TownLayout
    {
        public const string GroundArt = "art/town-ground";
        public static readonly Vector2 GroundSize = new(3200f, 2048f);

        /// <summary>70 個擺設（建築 + 裝飾）。</summary>
        public static readonly ForestProp[] Props =
        {
            new() { Art = "art/town-tiles/bush-n06", X = -167.0f, Y = 1083.2f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n15", X = -696.1f, Y = 1071.9f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n11", X = 331.8f, Y = 1062.2f, Scale = 1f },
            new() { Art = "art/town-tiles/fence-n01", X = 1534.5f, Y = 1050.9f, Scale = 1f },
            new() { Art = "art/town-tiles/arch", X = 639.0f, Y = 1042.5f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n15", X = 2038.2f, Y = 1002.9f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n03", X = 2142.9f, Y = 991.6f, Scale = 1f },
            new() { Art = "art/town-tiles/lamp-small", X = 514.8f, Y = 842.0f, Scale = 1f },
            new() { Art = "art/town-tiles/lamp-small", X = 764.8f, Y = 830.6f, Scale = 1f },
            new() { Art = "art/town/spell-shop", X = -209.0f, Y = 787.4f, Scale = 1f },
            new() { Art = "art/town-tiles/planter", X = -260.1f, Y = 770.6f, Scale = 1f },
            new() { Art = "art/town/potion-shop", X = 163.3f, Y = 769.4f, Scale = 1f },
            new() { Art = "art/town-tiles/planter", X = -581.0f, Y = 732.2f, Scale = 1f },
            new() { Art = "art/town-tiles/lamp-small", X = 515.3f, Y = 721.7f, Scale = 1f },
            new() { Art = "art/town-tiles/lamp-small", X = 774.1f, Y = 721.7f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n15", X = 1348.5f, Y = 656.4f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n05", X = 80.0f, Y = 620.0f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n15", X = 170.0f, Y = 620.0f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n03", X = 1312.0f, Y = 601.8f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n14", X = 130.0f, Y = 600.0f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n15", X = -520.0f, Y = 600.0f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n06", X = 1368.9f, Y = 597.7f, Scale = 1f },
            new() { Art = "art/town-tiles/bridge-stone", X = 1872.7f, Y = 567.1f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n15", X = -180.0f, Y = 540.0f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n11", X = -414.3f, Y = 539.0f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n15", X = -464.5f, Y = 502.1f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n06", X = -241.6f, Y = 466.9f, Scale = 1f },
            new() { Art = "art/town/flower-shop", X = 1191.6f, Y = 430.9f, Scale = 1f },
            new() { Art = "art/town/general-store", X = 198.7f, Y = 428.2f, Scale = 1f },
            new() { Art = "art/town-tiles/planter", X = 1129.3f, Y = 422.7f, Scale = 1f },
            new() { Art = "art/town-tiles/lamp-post", X = 978.6f, Y = 420.5f, Scale = 1f },
            new() { Art = "art/town-tiles/lamp-post", X = 339.9f, Y = 419.6f, Scale = 1f },
            new() { Art = "art/town-tiles/lamp-post", X = 34.9f, Y = 418.2f, Scale = 1f },
            new() { Art = "art/town-tiles/planter", X = 164.1f, Y = 414.5f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n06", X = 1590.5f, Y = 412.9f, Scale = 1f },
            new() { Art = "art/town-tiles/fence-lamp", X = -120.3f, Y = 410.3f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n02", X = -816.9f, Y = 404.7f, Scale = 1f },
            new() { Art = "art/town/cottage-home", X = -538.1f, Y = 390.0f, Scale = 1f },
            new() { Art = "art/town-tiles/bridge-wood-a", X = 1804.9f, Y = 320.0f, Scale = 1f },
            new() { Art = "art/town-tiles/fountain", X = 635.0f, Y = 256.6f, Scale = 1f },
            new() { Art = "art/town-tiles/lamp-post", X = 351.7f, Y = 188.6f, Scale = 1f },
            new() { Art = "art/town-tiles/lamp-post", X = 34.9f, Y = 186.8f, Scale = 1f },
            new() { Art = "art/town-tiles/fence-lamp", X = -122.7f, Y = 185.3f, Scale = 1f },
            new() { Art = "art/town-tiles/lamp-post", X = 979.7f, Y = 180.0f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n15", X = -440.5f, Y = 174.5f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n06", X = -628.4f, Y = 157.8f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n06", X = -538.2f, Y = 144.1f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n14", X = 1160.6f, Y = 131.6f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n15", X = 1058.9f, Y = 121.6f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n15", X = -701.7f, Y = 115.6f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n04", X = 0.0f, Y = 60.0f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n15", X = 80.0f, Y = 40.0f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n13", X = -75.0f, Y = -13.9f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n06", X = 1100.8f, Y = -53.7f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n03", X = 940.0f, Y = -60.0f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n13", X = -40.2f, Y = -72.9f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n14", X = -397.5f, Y = -84.7f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n06", X = 301.2f, Y = -89.9f, Scale = 1f },
            new() { Art = "art/town-tiles/fence-n04", X = 532.7f, Y = -127.1f, Scale = 1f },
            new() { Art = "art/town/scroll-shop", X = 132.8f, Y = -127.4f, Scale = 1f },
            new() { Art = "art/town-tiles/fence-lamp", X = 1338.7f, Y = -134.5f, Scale = 1f },
            new() { Art = "art/town-tiles/bridge-wood-b", X = 1787.8f, Y = -200.0f, Scale = 1f },
            new() { Art = "art/town-tiles/fence-n01", X = 1058.2f, Y = -310.3f, Scale = 1f },
            new() { Art = "art/town-tiles/fence-lamp", X = 629.1f, Y = -311.7f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n02", X = 1590.0f, Y = -340.0f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n16", X = -222.4f, Y = -469.3f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n02", X = 460.0f, Y = -520.0f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n09", X = 1340.0f, Y = -520.0f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n06", X = 410.0f, Y = -520.0f, Scale = 1f },
            new() { Art = "art/town-tiles/bush-n15", X = 1390.0f, Y = -520.0f, Scale = 1f },
        };
    }
}
