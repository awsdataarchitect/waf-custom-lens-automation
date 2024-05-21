
#### `CHANGELOG.md`:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - 2024-05-21
### Added
- Automated workload creation in AWS Well-Architected Tool.
- Applied custom lens to workload.
- Answered lens questions based on provided JSON.
- Generated and uploaded Well-Architected Reports to S3.
- Lambda function code enhanced for the above functionality.

## [0.2.0] - 2024-05-20
### Added
- Integrated AWS CDK for infrastructure as code setup.
- Created an S3 bucket for storing custom lens JSON files.
- Set up a Lambda function triggered by S3 events.
- Implemented Lambda to process S3 uploads and create custom lenses in AWS Well-Architected Tool.
- Added architecture diagram generation using Mermaid.


## [0.1.0] - 2024-05-17
### Added
- Initial release with custom lens upload functionality.