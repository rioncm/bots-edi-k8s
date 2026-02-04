# Makefile: Bots plugins
#
# Bots: open source edi translator
#
# author: Ludovic Watteaux

.DEFAULT_GOAL := all

date ?= $(shell date +%Y%m%d)
time ?= $(shell date +T%H%M%S)
ts ?= $(date)
# ts ?= $(date)$(time)
BUILD_DIR := ${CURDIR}/build/$(ts)

plugin_types := x12 edifact tradacoms demo
bots_plugins := $(wildcard x12/* edifact/* tradacoms/* demo/*)

.PHONY: infos
infos:
	@(echo "CURDIR: $(CURDIR)")
	@(echo "BUILD_DIR: $(BUILD_DIR)")

.PHONY: list_bots_plugins
list_bots_plugins:
	@(echo "Bots plugins: $(bots_plugins)")

.PHONY: $(BUILD_DIR)
$(BUILD_DIR):
	@(mkdir -pv $@)
	@(for plugtype in $(plugin_types); do\
		mkdir -pv "$@/$${plugtype}";\
	done)

.PHONY: all
all: infos $(bots_plugins)

# Build bots plugins
$(bots_plugins): $(BUILD_DIR)
	@(echo "Creating bots plugin: $@")
	cd $@ && zip -r $(BUILD_DIR)/$@_$(ts).zip ./
