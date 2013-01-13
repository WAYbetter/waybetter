<!-- uncomment for jsp file -->
<!--
<%@ page language="java" contentType="text/html; charset=utf-8"
	pageEncoding="utf-8" errorPage="/error.jsp"%>

<jsp:useBean id="transactionDetails" scope="request" type="com.creditguard.common.transactions.TransactionDetails" />
<%@ include file="/merchantPages/WebSources/includes/main.jsp" %>
-->

<%
String langdir="ltr";
String absvertpos="right: 0";
if(lang.equals("HE")){
    langdir="rtl";
    absvertpos="left: 0";
}
%>

{% extends "wb_base_mobile.html" %}
{% load i18n %}

{% block extrastyle %}
    {{ block.super }}
    <style type="text/css">
        body {
            direction: <%=langdir%>;
        }
        select {
            width: 100%;
            height: 33px;
            border-radius: 0;
            -webkit-border-radius: 0;
            -moz-border-radius: 0;
        }
        input[type="text"], input[type="tel"]{
            width: 100%;
            height: 33px;
        }

        div[data-role="header"] h1{
            line-height: 1;
        }
        #payment-header{
            color: white;
        }

        #wb_CVVhelp {
            width: 225px;
            height: 125px;
            display: block;
            background: url("/static/images/wb_site/cvv.png") left 0 no-repeat;
        }

        #qm {
            display: inline-block;
            height: 18px;
            width: 18px;
            position: relative;
            top: 3px;
            cursor: pointer;
            background: url("/static/images/wb_site/question_mark.png") left 0 no-repeat;
            <% if (langdir.equals("ltr")) { %>
                margin-left: 30px;
            <% } else { %>
                margin-right: 30px;
            <% } %>

        }

        #cvv {
            display: inline-block;
            width: 47%;
        }

        #lock {
            width: 90px;
            height: 90px;
            background: url("/static/images/wb_site/pci_lock.png") left center no-repeat;
        }

        label.ui-input-text, label.ui-select {
            margin-top: 10px;
        }

        #personalId {
            margin-bottom: 40px;
        }

    </style>

{% endblock %}

{% block extrahead %}
    {{ block.super }}
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta http-equiv="cache-control" content="no-cache">
    <meta http-equiv="pragma" content="no-cache">
    <meta http-equiv="expires" content="-1">
    <script src="merchantPages/WebSources/js/<%=lang%>.js"></script>
    <script src="merchantPages/WebSources/js/main.js"></script>
{% endblock %}

{% block body %}
    <div id="credit_guard_page" data-role="page" data-theme="a">
        <div data-role="header" class="top-header ui-header ui-bar-a" role="banner">
            <div class="header-center ng-binding">
                <% if (lang.equals("HE")) { %>
                    אמצעי תשלום
                <% } else { %>
                    Payment Method
                <% } %>
            </div>
        </div>

        <div data-role="content">
            <table id="payment-header">
                <tr>
                    <td id="lock"></td>
                    <td>
                        <span class="bold">
                            <% if (lang.equals("HE")) { %>
                                תשלום מאובטח
                            <% } else { %>
                                Secured Payment
                            <% } %>
                        </span>
                        <br>
                        <% if (lang.equals("HE")) { %>
                            התשלום עבור הנסיעות בלבד
                        <% } else { %>
                            Payments are for rides only
                        <% } %>
                        <br>
                        <% if (lang.equals("HE")) { %>
                            החיוב מתבצע לאחר ביצוע הנסיעות
                        <% } else { %>
                            Charging is only after your pickup
                        <% } %>
                        <br>
                        <% if (lang.equals("HE")) { %>
                            חשבונית חודשית מפורטת נשלחת במייל
                        <% } else { %>
                            Monthly invoice will be sent by email
                        <% } %>
                    </td>
                </tr>
            </table>

            <hr>

            <form id="creditForm" onsubmit="return formValidator(0);" method="POST" action="ProcessCreditCard">
                <input data-role="none" type="hidden" name="txId" value="<%=mpiTxnId%>"/>
                <input data-role="none" type="hidden" name="lang" value="EN"/>
                <input data-role="none" type="hidden" name="track2" value="" autocomplete="off"/>
                <input data-role="none" type="hidden" name="last4d" value="" autocomplete="off"/>
                <input data-role="none" type="hidden" name="cavv" value="" autocomplete="off"/>
                <input data-role="none" type="hidden" name="eci" value="" autocomplete="off"/>
                <input data-role="none" type="hidden" name="transactionCode" value="Phone" autocomplete="off"/>

                <label for="cardNumber"><%=CCNumber%></label>
                <input data-role="none" type="tel" id="cardNumber" name="cardNumber" maxlength="19" autocomplete="off"/>

                <label for="expYear"><%=CCExp%></label>

                <div>
                    <table style="width: 100%">
                        <tr>
                            <td style="width: 47%">
                                <select data-role="none" id="expYear" name="expYear">
                                    <%=expYear%>
                                </select>
                            </td>
                            <td></td>
                            <td style="width: 47%">
                                <select data-role="none" id="expMonth" name="expMonth">
                                    <option value="01">01</option>
                                    <option value="02">02</option>
                                    <option value="03">03</option>
                                    <option value="04">04</option>
                                    <option value="05">05</option>
                                    <option value="06">06</option>
                                    <option value="07">07</option>
                                    <option value="08">08</option>
                                    <option value="09">09</option>
                                    <option value="10">10</option>
                                    <option value="11">11</option>
                                    <option value="12">12</option>
                                </select>
                            </td>
                        </tr>
                    </table>
                </div>

                <label for="cvv">CVV</label>
                <input data-role="none" type="tel" name="cvv" id="cvv" maxlength="4" autocomplete="off"/>
                <a href="#cvv_dialog" data-rel="dialog">
                    <span id="qm" src="merchantPages/WebSources/images/qm.png"></span>
                </a>


                <label for="personalId"><%=CCPId%></label>
                <input data-role="none" type="tel" id="personalId" name="personalId" maxlength="9" autocomplete="off"/>

                <input type="submit" id="submitBtn" value="<%=formSend%>" class="btn btn-block btn-info btn-large" data-role="none"/>
                <div class="hidden">
                    {# need this to avoid js errors from CreditGuard's scripts #}
                    <input id="resetBtn" type="reset" value="<%=formReset%>"/>
                </div>
            </form>
        </div>
    </div>

    <div id="cvv_dialog" data-role="page">
        <div data-role="header">
            <h1>CVV</h1>
        </div>
        <div data-role="content">
            <span id="wb_CVVhelp"></span>
        </div>
    </div>
{% endblock body %}

{% block doc_ready %}
    {{ block.super }}
    <script type="text/javascript">
        $(document).ready(function() {
            $.mobile.ajaxEnabled = false;

            $("#cardNumber, #cvv, #personalId").keyup(function() {
                var valid = Boolean($("#cardNumber").val() && $("#cvv").val() && $("#personalId").val());
                if (valid){
                    $("#submitBtn").enable();
                }
                else{
                    $("#submitBtn").disable();
                }
            }).trigger("keyup");
        });

    </script>
{% endblock %}