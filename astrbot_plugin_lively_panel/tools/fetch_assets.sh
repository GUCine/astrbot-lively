# 面板素材一鍵安裝：把 Live2D 形象需要的庫和模型整理進 static/live2d/（倉庫不附帶第三方素材，這個腳本從來源取）
# 用法：
#   bash tools/fetch_assets.sh            只裝三個庫（Cubism Core、pixi.js、pixi-live2d-display），不放形象
#   bash tools/fetch_assets.sh 模型.zip   再把 DeepSeek-chan 免費模型的 zip 轉成面板用的檔案（要 ffmpeg、cwebp、unzip）
# 需要：curl、npm、python3。模型 zip 到作者發佈頁下載：立繪 神宮涼子 Kamiya Ryoko（https://vgen.co/KAMIYA）、Live2D 霓虹貓_NeonNeko
# 授權：模型可免費個人使用，不能轉載、不能把模型檔放出去給人下載；所以只放自己的部署，別提交進任何倉庫
# 三個庫：Cubism Core 5（Live2D 官方，可隨應用再發布）、pixi.js 6.5.10（MIT）、pixi-live2d-display 0.4.0（MIT，用 patch_l2d.py 補上 Cubism 4.2 的乘色、屏幕色）
# 表情包：到梗鯨 https://aigengtu.com/ 挑圖，轉成 .webp 放 static/meme/（檔名見 README）；標題字體：https://github.com/PC2005-cloud/dsh-pet 取得，放 static/font/rt.woff2
set -e
P=$(cd "$(dirname "$0")" && pwd)
OUT=$P/../static/live2d
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$OUT/lib"
cd "$T"
npm pack pixi.js@6.5.10 pixi-live2d-display@0.4.0 --silent >/dev/null
mkdir px pl && tar xzf pixi.js-6.5.10.tgz -C px && tar xzf pixi-live2d-display-0.4.0.tgz -C pl && chmod -R u+rwX px pl
cp px/package/dist/browser/pixi.min.js "$OUT/lib/"
python3 -I "$P/patch_l2d.py" pl/package/dist/cubism4.js "$OUT/lib/cubism4.js"
curl -fsSL -o "$OUT/lib/live2dcubismcore.min.js" https://cubism.live2d.com/sdk-web/cubismcore/live2dcubismcore.min.js
for f in "$OUT"/lib/*.js; do gzip -9 -k -f "$f"; done
if [ -n "$1" ]; then
ZIP=$1
VER=dsc-1031  # 换了模型或贴图要改这个名字（静态文件长快取 30 天），avatar.json 的 model 跟着改
unzip -q "$ZIP" -d "$T/zip"
S=$(dirname "$(find "$T/zip" -name '*.model3.json' | head -1)")
rm -rf "$OUT/$VER" && mkdir -p "$OUT/$VER"
M=$OUT/$VER
cp "$S"/*.moc3 "$M/dsc.moc3"
cp "$S"/*.physics3.json "$M/dsc.physics3.json"
cp "$S/Animation/IDLE.motion3.json" "$M/idle.motion3.json"
i=0
for f in "$S"/*.4096/texture_0?.png; do
  ffmpeg -loglevel error -y -i "$f" -vf scale=iw/2:ih/2:flags=lanczos -pix_fmt rgba "$T/t.png"
  cwebp -quiet -q 90 -alpha_q 100 -exact "$T/t.png" -o "$M/t$i.webp"
  i=$((i + 1))
done
cat > "$M/dsc.model3.json" <<'JSON'
{
	"Version": 3,
	"FileReferences": {
		"Moc": "dsc.moc3",
		"Textures": ["t0.webp", "t1.webp", "t2.webp", "t3.webp", "t4.webp"],
		"Physics": "dsc.physics3.json",
		"Motions": {"Idle": [{"File": "idle.motion3.json"}]}
	},
	"Groups": [
		{"Target": "Parameter", "Name": "EyeBlink", "Ids": ["ParamEyeROpen", "ParamEyeLOpen"]},
		{"Target": "Parameter", "Name": "LipSync", "Ids": []}
	]
}
JSON
cp "$S"/../*Terms*Setup*.txt "$M/LICENSE-model.txt" 2>/dev/null || true
cat > "$M/CREDITS.txt" <<'TXT'
DeepSeek-chan（大肥鱼）免费 Live2D 模型
立绘、PSD 拆分：神宫凉子 Kamiya Ryoko（https://vgen.co/KAMIYA，@kamiya_ryoko）
Live2D 建模：霓虹猫_NeonNeko
只在小肥鱼的面板里用：文件名改成英文、贴图缩小，其余没动；不转卖、不放出去给人下载
TXT
for f in "$M/dsc.moc3" "$M/dsc.physics3.json" "$M/idle.motion3.json" "$M/dsc.model3.json"; do gzip -9 -k -f "$f"; done
fi
ls -la "$OUT" "$OUT/lib"
