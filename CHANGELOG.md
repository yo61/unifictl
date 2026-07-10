# Changelog

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
