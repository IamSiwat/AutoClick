# AutoClick

Auto mouse clicker for Windows with GUI. Supports both repeated clicking at a fixed interval and sequential clicking at recorded positions. Works with games and elevated applications using the Windows `SendInput` API.

## Features

### Interval Mode
- Click repeatedly at the current cursor position
- Configurable interval: hours, minutes, seconds, milliseconds
- Mouse button: left / right / middle
- Click type: single / double
- Repeat: unlimited or a specific number of clicks

### Sequence Mode
- Record multiple click positions on screen
- Replay clicks in order with configurable delay between points
- Add or remove individual points from the list
- Repeat: unlimited loops or a specific number of rounds

### Hotkeys
| Key | Action |
|-----|--------|
| `F6` | Start / Stop |
| `ESC` | Emergency stop |

### Other
- Real-time cursor coordinates display
- Auto-elevates to Administrator for reliable input injection
- Uses Windows `SendInput` API for game compatibility

## Screenshot

![AutoClick](https://github.com/user-attachments/assets/autoclick-screenshot.png)

## Requirements

- Windows 10 / 11
- Python 3.8+

## Installation

```bash
git clone https://github.com/IamSiwat/AutoClick.git
cd AutoClick
pip install -r requirements.txt
```

## Usage

### Run from source
```bash
python autoclick.py
```

### Build standalone .exe
```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name AutoClick --uac-admin autoclick.py
```

The executable will be in the `dist/` folder. Double-click `AutoClick.exe` to run — no Python installation needed.

## How It Works

1. **Interval Mode** - Set the desired click speed and press `F6`. The program clicks at whatever position your cursor is currently at.
2. **Sequence Mode** - Click "Start Recording", click the positions you want on screen, then click "Stop Recording". Press `F6` to replay all recorded clicks in order.

## License

MIT
