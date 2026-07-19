BADGE_APP_DIR := /apps/zemlab_tildagon_snake
BADGE_APP_FILES := app.py __init__.py metadata.json

.PHONY: install
install:
	mpremote mkdir $(BADGE_APP_DIR) 2>/dev/null || true
	mpremote cp $(BADGE_APP_FILES) :$(BADGE_APP_DIR)/
	mpremote reset
