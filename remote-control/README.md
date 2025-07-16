# radio-pad remote-control

Remotely control [radio-pad](https://github.com/briceburg/radio-pad) through a simple web and/or mobile application.

## Overview

* remote controls connect via websockets to an instance of [switchboard](../switchboard/) -- which is used as a event-driven communication bus.
  * remote controls publish requested stations and listen for channel changes.
  * the player listens for requested stations and publishes channel changes.  
* [capacitor](https://capacitorjs.com) and [ionic framework](https://ionicframework.com/) v8 are used to build native mobile and static web controls.
  * VanillaJS is used instead of react/angular. this is a KISS project.

## Usage

### Configure the Application

```bash
npm install
npx cap add android
```

### Running the Application

**Web/Local Development:**

To run the app in a local web browser for development and testing:

```bash
npm start
```

**Android:**

> requires an Android SDK

To build and run the application on an Android device or emulator:

```bash
npm run build
npx cap run android
```

## Development

### Contributing

Pull requests and bug reports are welcome! Please [open an issue](https://github.com/briceburg/radio-pad/issues) or submit a PR.

## Support

For questions or help, please open an issue on the [GitHub repository](https://github.com/briceburg/radio-pad/issues).

## License

[BSD 3-Clause "New" or "Revised" License](./LICENSE)
