# 給 pixi-live2d-display 0.4.0 的 cubism4.js 補上 Cubism 4.2 的乘色、屏幕色（這個模型的臉、眼睛靠它上色，不補就是黑的）
import sys
src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding="utf-8").read()
def rep(a, b, n=1):
    global s
    assert s.count(a) == n, (a[:60], s.count(a))
    s = s.replace(a, b)
COL = "vec4 texColor = texture2D(s_texture0, v_texCoord);texColor.rgb = texColor.rgb * u_multiplyColor.rgb;texColor.rgb = (texColor.rgb + u_screenColor.rgb * texColor.a) - (texColor.rgb * u_screenColor.rgb);"
U = "uniform vec4 u_multiplyColor;uniform vec4 u_screenColor;"
rep('const fragmentShaderSrcPremultipliedAlpha = "precision mediump float;varying vec2       v_texCoord;uniform vec4       u_baseColor;uniform sampler2D  s_texture0;void main(){   gl_FragColor = texture2D(s_texture0 , v_texCoord) * u_baseColor;}";',
    'const fragmentShaderSrcPremultipliedAlpha = "precision mediump float;varying vec2 v_texCoord;uniform vec4 u_baseColor;uniform sampler2D s_texture0;' + U + 'void main(){' + COL + 'gl_FragColor = texColor * u_baseColor;}";')
rep('uniform sampler2D  s_texture1;void main(){   vec4 col_formask = texture2D(s_texture0 , v_texCoord) * u_baseColor;',
    'uniform sampler2D  s_texture1;' + U + 'void main(){' + COL + 'vec4 col_formask = texColor * u_baseColor;')
rep('uniform vec4 u_baseColor;void main(){vec4 col_formask = texture2D(s_texture0, v_texCoord) * u_baseColor;',
    'uniform vec4 u_baseColor;' + U + 'void main(){' + COL + 'vec4 col_formask = texColor * u_baseColor;')
last = '      this._shaderSets[9].uniformBaseColorLocation = this.gl.getUniformLocation(this._shaderSets[9].shaderProgram, "u_baseColor");\n'
rep(last, last + '      for (let i = 1; i < 10; i++) {\n        this._shaderSets[i].uniformMultiplyColorLocation = this.gl.getUniformLocation(this._shaderSets[i].shaderProgram, "u_multiplyColor");\n        this._shaderSets[i].uniformScreenColorLocation = this.gl.getUniformLocation(this._shaderSets[i].shaderProgram, "u_screenColor");\n      }\n')
bc = '        this.gl.uniform4f(shaderSet.uniformBaseColorLocation, baseColor.R, baseColor.G, baseColor.B, baseColor.A);\n      }\n'
rep(bc, '        this.gl.uniform4f(shaderSet.uniformBaseColorLocation, baseColor.R, baseColor.G, baseColor.B, baseColor.A);\n'
    '        const di = renderer._drawableIndex, D = renderer.getModel().getModel().drawables, o = di * 4;\n'
    '        if (di >= 0 && D.multiplyColors) {\n'
    '          this.gl.uniform4f(shaderSet.uniformMultiplyColorLocation, D.multiplyColors[o], D.multiplyColors[o + 1], D.multiplyColors[o + 2], 1);\n'
    '          this.gl.uniform4f(shaderSet.uniformScreenColorLocation, D.screenColors[o], D.screenColors[o + 1], D.screenColors[o + 2], 1);\n'
    '        } else {\n'
    '          this.gl.uniform4f(shaderSet.uniformMultiplyColorLocation, 1, 1, 1, 1);\n'
    '          this.gl.uniform4f(shaderSet.uniformScreenColorLocation, 0, 0, 0, 1);\n'
    '        }\n      }\n')
rep('        this.setIsCulling(this.getModel().getDrawableCulling(drawableIndex));\n        this.drawMesh(',
    '        this.setIsCulling(this.getModel().getDrawableCulling(drawableIndex));\n        this._drawableIndex = drawableIndex;\n        this.drawMesh(')
s = "/* pixi-live2d-display 0.4.0 (MIT)：小肥鱼面板补了 Cubism 4.2 乘色、屏幕色，见 panel-dev/live2d/patch_l2d.py */\n" + s
open(dst, "w", encoding="utf-8").write(s)
print("ok")
