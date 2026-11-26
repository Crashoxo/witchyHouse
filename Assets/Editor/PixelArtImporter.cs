using UnityEditor;
using UnityEngine;

/// <summary>
/// Assets/Resources 底下的圖全是像素風小圖，Unity 的預設匯入設定（壓縮 + 雙線性過濾）
/// 會讓它們糊掉、髒掉。這個 AssetPostprocessor 在匯入當下就把設定改對，
/// 免得 260 張圖要一張一張手點。
///
/// ⚠️ PPU 設 1 是刻意的：原 Cocos 專案的座標全是像素值，1 單位＝1 像素才不用重調。
///    見 Assets/Scripts/Core/PortNotes.md。
/// </summary>
public class PixelArtImporter : AssetPostprocessor
{
    void OnPreprocessTexture()
    {
        // Unity 的 assetPath 一律是正斜線（Windows 上也是），所以不需要轉換路徑分隔符號。
        if (assetPath.IndexOf("/Resources/", System.StringComparison.Ordinal) < 0) return;
        // （Resources/items8/ 的 8-bit 道具圖示也走這條：96×96 純色格子，Point 不壓縮才不會糊，不用另外加規則）

        var ti = (TextureImporter)assetImporter;
        ti.textureType         = TextureImporterType.Sprite;
        ti.spriteImportMode    = SpriteImportMode.Single;   // 走圖在程式裡自己切，不用 Multiple
        ti.filterMode          = FilterMode.Point;          // 像素風命脈：不能內插
        ti.mipmapEnabled       = false;
        ti.spritePixelsPerUnit = 1f;                        // 1 單位 = 1 像素
        ti.alphaIsTransparency = true;
        ti.textureCompression  = TextureImporterCompression.Uncompressed;
        ti.wrapMode            = TextureWrapMode.Clamp;

        // ⚠️ UI 外觀圖（tools/gen_ui_skin.py → Resources/ui/skin8/）例外：PPU 要等於
        //    UIPanelSettings 的 Reference Sprite Pixels Per Unit（100）。
        //    UI Toolkit 拿 Sprite 當背景時，九宮格邊距（-unity-slice-*）與圖的原尺寸都會乘上
        //    「參考 PPU ÷ Sprite 的 PPU」—— PPU 1 就是 ×100：27px 的木框被放大到夾滿元素的一半，
        //    整個面板只剩一大塊一大塊的色塊（實機踩過）。PPU 100 → 倍率 1，圖的 1 px ＝ UI 的 1 單位。
        //    這些圖只在 UI 用、不進世界空間，改 PPU 不影響任何 SpriteRenderer。
        //    items8／icons8 等世界空間也會用到的圖**不能**改（場景座標依賴 PPU 1）。
        //    ⚠️ 這裡每次匯入都會重設：沒有這個例外的話，就算手改 meta 成 100，下次重匯入又會被打回 1。
        //    反過來，已經匯入過的圖光改這裡也不會自動重匯入 —— 要連 meta 的 spritePixelsToUnits 一起改（或右鍵 Reimport）。
        if (assetPath.IndexOf("/Resources/ui/skin8/", System.StringComparison.Ordinal) >= 0)
        {
            ti.spritePixelsPerUnit = 100f;
            // 九宮格要整張矩形，不要 Tight 網格（TextureImporter 沒有直接的屬性，要走 TextureImporterSettings）
            var st = new TextureImporterSettings();
            ti.ReadTextureSettings(st);
            st.spriteMeshType = SpriteMeshType.FullRect;
            ti.SetTextureSettings(st);
        }
    }
}
