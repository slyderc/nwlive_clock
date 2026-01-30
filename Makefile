all : mainscreen.py settings.py resources_rc.py

mainscreen.py : mainscreen.ui
	pyuic6 mainscreen.ui -o mainscreen.py
	@echo "import resources_rc  # noqa: F401" | cat - mainscreen.py > temp && mv temp mainscreen.py || true

settings.py : settings.ui
	pyuic6 settings.ui -o settings.py
	@echo "import resources_rc  # noqa: F401" | cat - settings.py > temp && mv temp settings.py || true

resources_rc.py : resources.qrc
	@rcc_path=""; \
	if command -v rcc >/dev/null 2>&1; then \
		rcc_path="rcc"; \
	elif [ -x /usr/lib/qt6/libexec/rcc ]; then \
		rcc_path="/usr/lib/qt6/libexec/rcc"; \
	elif [ -d /usr/local/Cellar/qt ]; then \
		rcc_path=$$(find -L /usr/local/Cellar/qt -name rcc -type f 2>/dev/null | head -1); \
	elif [ -d /opt/homebrew/Cellar/qt ]; then \
		rcc_path=$$(find -L /opt/homebrew/Cellar/qt -name rcc -type f 2>/dev/null | head -1); \
	fi; \
	if [ -n "$$rcc_path" ]; then \
		$$rcc_path -g python -o resources_rc.py resources.qrc && \
		if [ "$$(uname)" = "Darwin" ]; then \
			sed -i '' 's/from PySide6/from PyQt6/g' resources_rc.py; \
		else \
			sed -i 's/from PySide6/from PyQt6/g' resources_rc.py; \
		fi; \
	else \
		echo "Warning: rcc tool not found. Install qt6-tools-dev (Linux) or qt (macOS)."; \
	fi

clean cleandir:
	rm -rf $(CLEANFILES)

CLEANFILES = mainscreen.py settings.py resources_rc.py *.pyc
