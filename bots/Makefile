################################################
# Makefile for Bots open source edi translator #
################################################

# LOCALE MESSAGES
.PHONY: locales locale_fr locale_nl
locales: locale_fr locale_nl

locale_fr locale_nl: locale_%:
	@(cd bots && django-admin makemessages -l $* && django-admin compilemessages -l $*)
