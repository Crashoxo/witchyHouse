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

        var ti = (TextureImporter)assetImporter;
        ti.textureType         = TextureImporterType.Sprite;
        ti.spriteImportMode    = SpriteImportMode.Single;   // 走圖在程式裡自己切，不用 Multiple
        ti.filterMode          = FilterMode.Point;          // 像素風命脈：不能內插
        ti.mipmapEnabled       = false;
        ti.spritePixelsPerUnit = 1f;                        // 1 單位 = 1 像素
        ti.alphaIsTransparency = true;
        ti.textureCompression  = TextureImporterCompression.Uncompressed;
        ti.wrapMode            = TextureWrapMode.Clamp;
    }
}
