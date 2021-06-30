# Changelog

All notable changes to Nyantip will be documented in this file.

The format is based on [Keep a
Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3] - 2021/06/29

### Fixed

- Avoid flooding modlog with no-op wiki page updates.

## [0.2] - 2021/06/28

### Added

- Commands no longer need to be the only part of a message body, so long as
  they are the only thing on their own line
- Log when an action is ignored because it can either only appear in a `Comment`
  or in a direct `Message`
- Setting `exception_user` to send stacktraces to when message handling results
  in an exception

### Fixed

- Avoid needing to refresh `Comment` mentions to obtain their `permalink`; the
  `context` attribute is used instead
- Exceptions that occur as part of processing a message will be logged and no
  longer cause the program to exit
- Handle 403 `Forbidden` exceptions when attempting to reply to a `Comment` or
  direct `Message`
- Periodic tasks were not running because their initial `next_run_time` was
  never set
- Rollback wallet `move` actions when there is an exception when saving the status


## [0.1] - 2021/06/26

### Added

- Initial version of this nyantip package released to pypi. The code was significantly
  modified from its prior source.
