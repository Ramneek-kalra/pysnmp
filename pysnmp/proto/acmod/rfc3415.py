#
# This file is part of pysnmp software.
#
# Copyright (c) 2005-2019, Ilya Etingof <etingof@gmail.com>
# License: http://snmplabs.com/pysnmp/license.html
#
from pysnmp import debug
from pysnmp.proto import errind
from pysnmp.proto import error
from pysnmp.smi.error import NoSuchInstanceError


# 3.2
class Vacm(object):
    """View-based Access Control Model"""
    ACCESS_MODEL_ID = 3

    _powOfTwoSeq = (128, 64, 32, 16, 8, 4, 2, 1)

    def isAccessAllowed(self, snmpEngine, securityModel, securityName,
                        securityLevel, viewType, contextName, variableName):

        mibInstrumController = snmpEngine.msgAndPduDsp.mibInstrumController
        mibBuilder = mibInstrumController.mibBuilder

        debug.logger & debug.FLAG_ACL and debug.logger(
            'isAccessAllowed: securityModel %s, securityName %s, '
            'securityLevel %s, viewType %s, contextName %s for '
            'variableName %s' % (securityModel, securityName, securityLevel,
                                 viewType, contextName, variableName))

        # 3.2.1
        vacmContextEntry, = mibBuilder.importSymbols(
            'SNMP-VIEW-BASED-ACM-MIB', 'vacmContextEntry')

        tblIdx = vacmContextEntry.getInstIdFromIndices(contextName)

        try:
            vacmContextEntry.getNode(
                vacmContextEntry.name + (1,) + tblIdx).syntax

        except NoSuchInstanceError:
            raise error.StatusInformation(errorIndication=errind.noSuchContext)

        # 3.2.2
        vacmSecurityToGroupEntry, = mibBuilder.importSymbols(
            'SNMP-VIEW-BASED-ACM-MIB', 'vacmSecurityToGroupEntry')

        tblIdx = vacmSecurityToGroupEntry.getInstIdFromIndices(
            securityModel, securityName)

        try:
            vacmGroupName = vacmSecurityToGroupEntry.getNode(
                vacmSecurityToGroupEntry.name + (3,) + tblIdx).syntax

        except NoSuchInstanceError:
            raise error.StatusInformation(errorIndication=errind.noGroupName)

        # 3.2.3
        vacmAccessEntry, = mibBuilder.importSymbols(
            'SNMP-VIEW-BASED-ACM-MIB', 'vacmAccessEntry')

        # XXX partial context name match
        tblIdx = vacmAccessEntry.getInstIdFromIndices(
            vacmGroupName, contextName, securityModel, securityLevel)

        # 3.2.4
        if viewType == 'read':
            entryIdx = vacmAccessEntry.name + (5,) + tblIdx

        elif viewType == 'write':
            entryIdx = vacmAccessEntry.name + (6,) + tblIdx

        elif viewType == 'notify':
            entryIdx = vacmAccessEntry.name + (7,) + tblIdx

        else:
            raise error.ProtocolError('Unknown view type %s' % viewType)

        try:
            viewName = vacmAccessEntry.getNode(entryIdx).syntax

        except NoSuchInstanceError:
            raise error.StatusInformation(errorIndication=errind.noAccessEntry)

        if not viewName:
            raise error.StatusInformation(errorIndication=errind.noSuchView)

        # XXX split onto object & instance ?

        # 3.2.5a
        vacmViewTreeFamilyEntry, = mibInstrumController.mibBuilder.importSymbols(
            'SNMP-VIEW-BASED-ACM-MIB', 'vacmViewTreeFamilyEntry')

        tblIdx = vacmViewTreeFamilyEntry.getInstIdFromIndices(viewName)

        # Walk over entries
        initialTreeName = treeName = vacmViewTreeFamilyEntry.name + (2,) + tblIdx

        maskName = vacmViewTreeFamilyEntry.name + (3,) + tblIdx

        while True:
            vacmViewTreeFamilySubtree = vacmViewTreeFamilyEntry.getNextNode(
                treeName)

            vacmViewTreeFamilyMask = vacmViewTreeFamilyEntry.getNextNode(
                maskName)

            treeName = vacmViewTreeFamilySubtree.name
            maskName = vacmViewTreeFamilyMask.name

            if initialTreeName != treeName[:len(initialTreeName)]:
                # 3.2.5b
                raise error.StatusInformation(errorIndication=errind.notInView)

            l = len(vacmViewTreeFamilySubtree.syntax)
            if l > len(variableName):
                continue

            if vacmViewTreeFamilyMask.syntax:
                mask = []
                for c in vacmViewTreeFamilyMask.syntax.asNumbers():
                    mask.extend([b & c for b in self._powOfTwoSeq])

                m = len(mask) - 1
                idx = l - 1

                while idx:
                    if (idx > m or mask[idx] and
                            vacmViewTreeFamilySubtree.syntax[idx] != variableName[idx]):
                        break

                    idx -= 1

                if idx:
                    continue  # no match

            else:  # no mask
                if vacmViewTreeFamilySubtree.syntax != variableName[:l]:
                    continue  # no match

            # 3.2.5c
            return error.StatusInformation(errorIndication=errind.accessAllowed)
