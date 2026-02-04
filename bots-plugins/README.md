# Bots-EDI plugins

## Description

[Bots-EDI](https://bots-edi.org) in its default configuration does nothing. It needs a configuration (syntax definition for input and output EDI files, mappings, channels, routes and translations).

When learning how Bots work or to speed up the creation of your own configuration, you can use sample plugins.

This repository contains the source code of plugins adapted to Bots NG version (Python3). Original plugins for Bots 3.2 (Frozen) are to be found at [SourceForge.net](https://sourceforge.net/projects/bots/files/plugins/).

## Usage
The latest ZIP files are available for download in our [Bots Plugins package registry](https://gitlab.com/bots-ediint/bots-plugins/-/packages/). 

You can also clone this repository and make all plugins locally:

```bash
git clone https://gitlab.com/bots-ediint/bots-plugins
cd bots-plugins
make
```
Choose the plugin from _build directory and upload it to bots. Remember to clean your bots instance before uploading a new plugin. Read [Plugins documentation](https://bots.readthedocs.io/en/latest/plugins/index.html) for more.

## Authors and acknowledgment

This set of plugins was originally made available by Henk-Jan Ebbers. Contributors: Mike Griffin and other bots community members. Adaptation to Python 3, cleanup and tests with Bots NG: Wojtek Kazimierczak.

## License

These plugins are licenced under GPL v.3.