# Original Xbox style Mashed: Fully Loaded for PC

This project is a fork of ([MFLng](https://github.com/mashed-reverse-engineering/MFL-recomp)) with a bunch of changes to make the physics and car handling match the original Xbox version exactly.

For example:

- **Analog triggers.** The gamepad triggers give proportional throttle and brake, as on the Xbox pad. (The old PC port treats them as on/off buttons). ([diff](https://github.com/eggsome/OG-Xbox-MFL-For-PC/commit/131cb4cc8d802bfa9f987e1c5304a89f665ce78f))
- **Xbox stick and D-pad handling.** Steering uses the Xbox version's dead zone and stick curve, and the D-pad ramps the steering the way it does on Xbox. ([diff](https://github.com/eggsome/OG-Xbox-MFL-For-PC/commit/7fb16a7b9f0e830cb1616ebc913bf0ba539ce0b1))
- **Rumble.** The PC game still generates the Xbox rumble requests but never sends them to a controller. Here they are played on the pad with the Xbox version's four motor patterns. ([diff](https://github.com/eggsome/OG-Xbox-MFL-For-PC/commit/eb8cdd1e55c05eb1fd4c3abe147dbaacc086f38b))
- **Exact square roots.** The PC game's graphics library takes square roots from a lookup table that is only accurate to about 4 parts in 100,000. The Xbox version uses the processor's exact square root. (this affects how cars interact with the road). ([diff](https://github.com/eggsome/OG-Xbox-MFL-For-PC/commit/3aade47296b873c2d3978c1fc42a4d3375b61a4f))
- **Ground alignment.** The Xbox version turns a car to follow the ground from 0.8 degrees of difference; the PC game waits until 2.6 degrees. The car follows small changes of slope as it does on Xbox. ([diff](https://github.com/eggsome/OG-Xbox-MFL-For-PC/commit/217b7afc2eb0274702db37c7977d79599a912d78))
- **Xbox menu font and button pictures.** The menus use the Xbox font, redrawn at high resolution, with the A / B / X / Y / START pictures and the Xbox controller picture in place of the PC keyboard and joystick ones. ([diff](https://github.com/eggsome/OG-Xbox-MFL-For-PC/commit/737cee08fa8a76562c20bbdfb862ca222b1864c8))

As per MFLng you will need to provide your own copy of the game to work with this code.
