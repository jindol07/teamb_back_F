from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

BASE_DIR = Path(__file__).resolve().parent.parent

IMAGE_PATH = BASE_DIR / "results" / "parking" / "first_frame.jpg"
SAVE_PATH = BASE_DIR / "data" / "parking_spaces" / "parking_spots.json"

SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)

HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>APCMS 주차면 좌표 편집기</title>
<style>
    body {
        font-family: Arial, sans-serif;
        margin: 20px;
        background: #f3f4f6;
    }
    h2 { margin-bottom: 8px; }
    p { color: #555; }
    .toolbar {
        margin: 15px 0;
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
    }
    button {
        padding: 9px 14px;
        cursor: pointer;
        border: 1px solid #bbb;
        border-radius: 5px;
        background: white;
    }
    button:hover { background: #e5e7eb; }
    #saveBtn {
        background: #2563eb;
        color: white;
        border-color: #2563eb;
    }
    #canvas {
        width: 100%;
        height: auto;
        display: block;
        cursor: crosshair;
    }
    .viewer {
        max-width: 1500px;
        border: 1px solid #ccc;
        background: white;
    }
    #status {
        font-weight: bold;
        margin: 12px 0;
    }
</style>
</head>
<body>

<h2>APCMS 주차면 영역 지정</h2>
<p>주차면의 네 모서리를 순서대로 클릭하세요.
네 점을 클릭하면 한 주차면이 등록됩니다.</p>

<div class="toolbar">
    <button onclick="undo()">마지막 클릭 취소</button>
    <button onclick="deleteLast()">마지막 주차면 삭제</button>
    <button onclick="resetAll()">전체 초기화</button>
    <button id="saveBtn" onclick="save()">JSON 저장</button>
</div>

<div id="status">이미지 로딩 중...</div>

<div class="viewer">
    <canvas id="canvas"></canvas>
</div>

<script>
const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");
const status = document.getElementById("status");

const image = new Image();
let spaces = [];
let currentPoints = [];

image.onload = () => {
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    draw();
};

image.onerror = () => {
    status.textContent = "이미지를 불러오지 못했습니다.";
};

image.src = "/image";

function spaceName(index) {
    return "A-" + String(index + 1).padStart(2, "0");
}

function drawPolygon(points, color, fill, closed) {
    if (points.length === 0) return;

    ctx.beginPath();
    ctx.moveTo(points[0][0], points[0][1]);

    for (let i = 1; i < points.length; i++) {
        ctx.lineTo(points[i][0], points[i][1]);
    }

    if (closed) {
        ctx.closePath();
        ctx.fillStyle = fill;
        ctx.fill();
    }

    ctx.strokeStyle = color;
    ctx.lineWidth = 4;
    ctx.stroke();

    for (const [x, y] of points) {
        ctx.beginPath();
        ctx.arc(x, y, 6, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
    }
}

function draw() {
    if (!image.complete || !image.naturalWidth) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(image, 0, 0);

    spaces.forEach((space, index) => {
        drawPolygon(
            space.points,
            "#00ff00",
            "rgba(0,255,0,0.18)",
            true
        );

        const x = space.points[0][0];
        const y = space.points[0][1];

        ctx.font = "bold 25px Arial";
        ctx.fillStyle = "#ffffff";
        ctx.strokeStyle = "#000000";
        ctx.lineWidth = 4;
        ctx.strokeText(space.id, x, y - 12);
        ctx.fillText(space.id, x, y - 12);
    });

    drawPolygon(
        currentPoints,
        "#ffff00",
        "rgba(255,255,0,0.15)",
        false
    );

    status.textContent =
        "등록된 주차면: " + spaces.length +
        "개 | 현재 입력: " + currentPoints.length +
        "/4점 | 다음: " + spaceName(spaces.length);
}

canvas.addEventListener("click", (event) => {
    const rect = canvas.getBoundingClientRect();

    // 화면에 축소 표시된 좌표를 원본 이미지 좌표로 변환
    const x = Math.round(
        (event.clientX - rect.left) *
        canvas.width / rect.width
    );

    const y = Math.round(
        (event.clientY - rect.top) *
        canvas.height / rect.height
    );

    currentPoints.push([x, y]);

    if (currentPoints.length === 4) {
        spaces.push({
            id: spaceName(spaces.length),
            points: [...currentPoints]
        });

        currentPoints = [];
    }

    draw();
});

function undo() {
    if (currentPoints.length > 0) {
        currentPoints.pop();
    } else if (spaces.length > 0) {
        currentPoints = spaces.pop().points;
        currentPoints.pop();
    }
    draw();
}

function deleteLast() {
    currentPoints = [];
    spaces.pop();
    draw();
}

function resetAll() {
    if (!confirm("모든 주차면 표시를 초기화할까요?")) return;
    spaces = [];
    currentPoints = [];
    draw();
}

async function save() {
    if (currentPoints.length !== 0) {
        alert("현재 주차면의 네 점을 모두 지정해주세요.");
        return;
    }

    if (spaces.length === 0) {
        alert("주차면을 먼저 등록해주세요.");
        return;
    }

    try {
        const response = await fetch("/save", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                image_width: canvas.width,
                image_height: canvas.height,
                spaces: spaces
            })
        });

        if (!response.ok) {
            throw new Error("HTTP " + response.status);
        }

        alert("주차면 좌표 저장 완료!");
    } catch (error) {
        alert("저장 실패: " + error.message);
    }
}

</script>
</body>
</html>
"""


class SpaceEditorHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        if self.path == "/":
            content = HTML.encode("utf-8")
            content_type = "text/html; charset=utf-8"

        elif self.path == "/image":
            if not IMAGE_PATH.exists():
                self.send_error(404, "Image not found")
                return

            content = IMAGE_PATH.read_bytes()
            content_type = "image/jpeg"

        else:
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):

        if self.path != "/save":
            self.send_error(404)
            return

        try:
            size = int(self.headers.get("Content-Length", "0"))

            if size <= 0 or size > 1024 * 1024:
                raise ValueError("Invalid request size")

            data = json.loads(self.rfile.read(size))

            width = data["image_width"]
            height = data["image_height"]
            spaces = data["spaces"]

            if not isinstance(spaces, list) or not spaces:
                raise ValueError("No parking spaces")

            for space in spaces:
                points = space["points"]

                if len(points) != 4:
                    raise ValueError("Each space needs 4 points")

                for x, y in points:
                    if not (0 <= x <= width and 0 <= y <= height):
                        raise ValueError("Point outside image")

            SAVE_PATH.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

            content = b'{"success":true}'
            self.send_response(200)

        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            content = b'{"success":false}'
            self.send_response(400)

        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


if __name__ == "__main__":

    if not IMAGE_PATH.exists():
        print("첫 프레임 이미지가 없습니다.")
        print(IMAGE_PATH)
        raise SystemExit(1)

    server = HTTPServer(("127.0.0.1", 8765), SpaceEditorHandler)

    print("=== 주차면 좌표 편집기 시작 ===")
    print("http://127.0.0.1:8765")
    print("종료: Ctrl+C")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
