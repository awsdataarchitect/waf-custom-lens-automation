#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { WellArchitectedToolStack } from '../lib/well_architected_tool-stack';

const app = new cdk.App();
new WellArchitectedToolStack(app, 'WellArchitectedToolStack');
