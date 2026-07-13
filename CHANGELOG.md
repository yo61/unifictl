# Changelog

## [0.4.0](https://github.com/yo61/unifictl/compare/v0.3.1...v0.4.0) (2026-07-13)


### Features

* configuration profiles with a separate credential store ([abce28a](https://github.com/yo61/unifictl/commit/abce28ab4d8d73a01ad8bbcefb2f8cbb8aa98d2d))

## [0.3.1](https://github.com/yo61/unifictl/compare/v0.3.0...v0.3.1) (2026-07-11)


### Documentation

* note Homebrew 24h bump-cooldown gotcha and remedy ([#7](https://github.com/yo61/unifictl/issues/7)) ([63bd40a](https://github.com/yo61/unifictl/commit/63bd40a436103c4437abda04f9132782ceec8a7d))

## [0.3.0](https://github.com/yo61/unifictl/compare/v0.2.0...v0.3.0) (2026-07-10)


### Features

* add completion command with install and self-heal ([9c95caa](https://github.com/yo61/unifictl/commit/9c95caa2d11b24829fbf15c236dac424d3c78170))
* add static __complete candidate handler ([20ba56b](https://github.com/yo61/unifictl/commit/20ba56b755071946e17fe2fc7bd768a89fe19dac))
* bundle per-shell completion scripts ([2594031](https://github.com/yo61/unifictl/commit/259403171e50d392052710589739640bf4809ab1))
* complete switch MACs and port indices from the controller ([3aae21a](https://github.com/yo61/unifictl/commit/3aae21a70163a1fbd979114d5357d10b524ee371))
* shell completion for bash, zsh, and fish ([59c6787](https://github.com/yo61/unifictl/commit/59c6787bf5043b3d6bab9d3d9bc7882e33ddb7c0))
* wire completion command and __complete fast-path into cli ([5f0af44](https://github.com/yo61/unifictl/commit/5f0af44f2436f2a98157a2f09873e66d3ebbedcf))


### Bug Fixes

* swallow all config errors in completion to never break the shell ([9a7b397](https://github.com/yo61/unifictl/commit/9a7b397256fb49e0b1c1fe0be6df533da415148d))


### Documentation

* design for shell completion ([bcd4b89](https://github.com/yo61/unifictl/commit/bcd4b8986c83664033feb13789e685a35b4d5026))
* document shell completion ([7ff9c8c](https://github.com/yo61/unifictl/commit/7ff9c8cc4af5d8f16011ea1f253af28d1acfceb6))
* fix zsh manual-wire completion path to match install default ([d87defa](https://github.com/yo61/unifictl/commit/d87defa52836047308a7cdf7a4d2cb09af933b6a))
* implementation plan for shell completion ([8b93b49](https://github.com/yo61/unifictl/commit/8b93b49be7ffdf7efb2860fa28525eeb295b2a04))
* note deliberate unguarded read in completion install ([6d30128](https://github.com/yo61/unifictl/commit/6d30128c2071536fa39abb16faacdabaea3ce837))
* record shell-completion plan amendments from execution ([647561d](https://github.com/yo61/unifictl/commit/647561db243ffe0eac00fb9794cd6dc12770c97f))

## [0.2.0](https://github.com/yo61/unifictl/compare/v0.1.0...v0.2.0) (2026-07-10)


### Features

* add list devices and show port read commands ([bde5591](https://github.com/yo61/unifictl/commit/bde55916bd40909ca9cf6896eb07d14c26b8e072))
* **app:** device read use-cases and PortNotFoundError ([4c54eeb](https://github.com/yo61/unifictl/commit/4c54eebcf7eb3d75cd91fbfb4af5e4fc3794af35))
* **cli:** list devices command ([9736330](https://github.com/yo61/unifictl/commit/9736330411b439e9471b429083bfca4ddc3e0281))
* **cli:** show port command ([735bc45](https://github.com/yo61/unifictl/commit/735bc457ecda1ee71dd923870526a5b591dd91a6))
* **domain:** describe_port and read value objects ([509b44f](https://github.com/yo61/unifictl/commit/509b44ff886127f1a9e3808fb75f731186b33f5c))
* **domain:** device_summary extraction ([21ffa16](https://github.com/yo61/unifictl/commit/21ffa16b4264d53dcf32577d96f97859c268e2fc))
* **infra:** add get_devices to the client ([b83f931](https://github.com/yo61/unifictl/commit/b83f9310a9fa3b27399ac39055c14afb83fc478b))


### Documentation

* design for list devices and show port read commands ([686a784](https://github.com/yo61/unifictl/commit/686a784f22876206b705843c7e1ffb362ff63955))
* generalise LAG command help and examples ([8e09387](https://github.com/yo61/unifictl/commit/8e09387ad8271e7ff5e67c5e9c0e8d50d46cb93c))
* generalise LAG command help and examples ([e935088](https://github.com/yo61/unifictl/commit/e9350889112c65988fda768cb15aa953b4a179ab))
* implementation plan for list devices and show port ([f12ec16](https://github.com/yo61/unifictl/commit/f12ec169a4d8aabb68f046cfcc037be2375bc26c))

## 0.1.0 (2026-07-09)


### Features

* **app:** implement set_aggregation use-case ([4246707](https://github.com/yo61/unifictl/commit/4246707a297c4a34bcebdb30a95b97bc0a9f5f4e))
* **cli:** implement set lag command with confirm and backup ([a840272](https://github.com/yo61/unifictl/commit/a8402727e3fef1407f4f871eeb7e91fad0ca5cf2))
* **domain:** implement LAG aggregation transform ([72cd7b9](https://github.com/yo61/unifictl/commit/72cd7b9b2e349679988ea973cc177d6a866b7cb9))
* **infra:** implement private-API client calls ([7b807bd](https://github.com/yo61/unifictl/commit/7b807bd664b730b1212c8b27d1e5406c67375acb))
* scaffold unifictl package skeleton ([f3ccb3f](https://github.com/yo61/unifictl/commit/f3ccb3f03cf568aea93ee559f421d37cf505ce48))


### Bug Fixes

* model LAG toggle as an op_mode flip, verified on hardware ([ea6764b](https://github.com/yo61/unifictl/commit/ea6764b6901de390a9dbe744317a4f2a35975a9d))
* model LAG toggle as an op_mode flip, verified on hardware ([49961b2](https://github.com/yo61/unifictl/commit/49961b2893caf19e9ab36495d74c6af31346068a))


### Documentation

* add build spec for unifictl skeleton and lag feature ([7a341ba](https://github.com/yo61/unifictl/commit/7a341ba2f80068935c7413d800451fb40e342e93))
* add shared-library plan for unifictl/unifi-mcp ([5692b73](https://github.com/yo61/unifictl/commit/5692b7310b6ec8ee26a4cbef9ca1c790662cc97f))
* add unifictl proposal summary ([3f3c17d](https://github.com/yo61/unifictl/commit/3f3c17d449c0b94e67d3a87207c2cccb80d8ab9f))
* lock private-API auth and drop shared-library premise ([ad15e7d](https://github.com/yo61/unifictl/commit/ad15e7d48ead2c9df3e33b70eaed8c01071e76e5))
* mark set lag feature as implemented ([93d6022](https://github.com/yo61/unifictl/commit/93d6022958a10a3dfcff677b24555bc4b19471ed))
* settle command name and distribution ([149f53a](https://github.com/yo61/unifictl/commit/149f53a806fcb0090729e39cf6ace8445c19a354))
